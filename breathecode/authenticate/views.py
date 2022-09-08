import os, logging
from urllib.parse import urlencode, parse_qs
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from .models import Token

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_token_info(request, token):

    token = Token.objects.filter(key=token).first()

    if token is None or token.expires_at < timezone.now():
        raise PermissionDenied('Expired or invalid token')

    return Response({
        'token': token.key,
        'token_type': token.token_type,
        'expires_at': token.expires_at,
        'user_id': token.user.pk
    })


class TemporalTokenView(ObtainAuthToken):
    schema = AutoSchema()
    permission_classes = [IsAuthenticated]

    def post(self, request):

        token, created = Token.get_or_create(user=request.user, token_type='temporal')
        return Response({
            'token': token.key,
            'token_type': token.token_type,
            'expires_at': token.expires_at,
            'user_id': token.user.pk,
            'email': token.user.email
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_github_token(request, token=None):

    url = request.query_params.get('url', None)
    if url == None:
        raise ValidationException('No callback URL specified', slug='no-callback-url')

    if token is not None:
        if Token.get_valid(token) is None:
            raise ValidationException('Invalid or missing token', slug='invalid-token')
        else:
            url = url + f'&user={token}'

    params = {
        'client_id': os.getenv('GITHUB_CLIENT_ID', ''),
        'redirect_uri': os.getenv('GITHUB_REDIRECT_URL', '') + f'?url={url}',
        'scope': 'user repo read:org',
    }

    logger.debug('Redirecting to github')
    logger.debug(params)

    redirect = f'https://github.com/login/oauth/authorize?{urlencode(params)}'

    if settings.DEBUG:
        return HttpResponse(f"Redirect to: <a href='{redirect}'>{redirect}</a>")
    else:
        return HttpResponseRedirect(redirect_to=redirect)


@api_view(['GET'])
@permission_classes([AllowAny])
def save_github_token(request):

    logger.debug('Github callback just landed')
    logger.debug(request.query_params)

    error = request.query_params.get('error', False)
    error_description = request.query_params.get('error_description', '')
    if error:
        raise APIException('Github: ' + error_description)

    url = request.query_params.get('url', None)
    if url == None:
        raise ValidationException('No callback URL specified', slug='no-callback-url')

    # the url may or may not be encoded
    try:
        url = base64.b64decode(url.encode('utf-8')).decode('utf-8')
    except Exception as e:
        pass

    code = request.query_params.get('code', None)
    if code == None:
        raise ValidationException('No github code specified', slug='no-code')

    token = request.query_params.get('user', None)

    payload = {
        'client_id': os.getenv('GITHUB_CLIENT_ID', ''),
        'client_secret': os.getenv('GITHUB_SECRET', ''),
        'redirect_uri': os.getenv('GITHUB_REDIRECT_URL', ''),
        'code': code,
    }
    headers = {'Accept': 'application/json'}
    resp = requests.post('https://github.com/login/oauth/access_token', data=payload, headers=headers)
    if resp.status_code == 200:

        logger.debug('Github responded with 200')

        body = resp.json()
        if 'access_token' not in body:
            raise APIException(body['error_description'])

        github_token = body['access_token']
        resp = requests.get('https://api.github.com/user', headers={'Authorization': 'token ' + github_token})
        if resp.status_code == 200:
            github_user = resp.json()
            logger.debug(github_user)

            if github_user['email'] is None:
                resp = requests.get('https://api.github.com/user/emails',
                                    headers={'Authorization': 'token ' + github_token})
                if resp.status_code == 200:
                    emails = resp.json()
                    primary_emails = [x for x in emails if x['primary'] == True]
                    if len(primary_emails) > 0:
                        github_user['email'] = primary_emails[0]['email']
                    elif len(emails) > 0:
                        github_user['email'] = emails[0]['email']

            if github_user['email'] is None:
                raise ValidationError('Impossible to retrieve user email')

            user = None  # assuming by default that its a new user
            # is a valid token??? if not valid it will become None
            if token is not None and token != '':
                token = Token.get_valid(token)
                if not token:
                    logger.debug(f'Token not found or is expired')
                    raise ValidationException(
                        'Token was not found or is expired, please use a different token',
                        code=404,
                        slug='token-not-found')
                user = User.objects.filter(auth_token=token.id).first()
            else:
                # for the token to become null for easier management
                token = None

            # user can't be found thru token, lets try thru the github credentials
            if token is None and user is None:
                user = User.objects.filter(credentialsgithub__github_id=github_user['id']).first()
                if user is None:
                    user = User.objects.filter(email__iexact=github_user['email'],
                                               credentialsgithub__isnull=True).first()

            user_does_not_exists = user is None
            if user_does_not_exists:
                invite = UserInvite.objects.filter(status='WAITING_LIST', email=github_user['email']).first()

            if user_does_not_exists and invite:
                if url is None or url == '':
                    url = os.getenv('APP_URL', 'https://4geeks.com')

                return render_message(
                    request,
                    f'You are still number {invite.id} on the waiting list, we will email you once you are '
                    f'given access <a href="{url}">Back to 4Geeks.com</a>')

            if user_does_not_exists:
                return render_message(
                    request, 'We could not find in our records the email associated to this github account, '
                    'perhaps you want to signup to the platform first? <a href="' + url +
                    '">Back to 4Geeks.com</a>')

            github_credentials = CredentialsGithub.objects.filter(github_id=github_user['id']).first()

            # update latest credentials if the user.id doesn't match
            if github_credentials and github_credentials.user.id != user.id:
                github_credentials.delete()
                github_credentials = None

            # create a new credentials if it doesn't exists
            if github_credentials is None:
                github_credentials = CredentialsGithub(github_id=github_user['id'], user=user)

            github_credentials.token = github_token
            github_credentials.username = github_user['login']
            github_credentials.email = github_user['email'].lower()
            github_credentials.avatar_url = github_user['avatar_url']
            github_credentials.name = github_user['name']
            github_credentials.blog = github_user['blog']
            github_credentials.bio = github_user['bio']
            github_credentials.company = github_user['company']
            github_credentials.twitter_username = github_user['twitter_username']
            github_credentials.save()

            profile = Profile.objects.filter(user=user).first()
            if profile is None:
                profile = Profile(user=user,
                                  avatar_url=github_user['avatar_url'],
                                  blog=github_user['blog'],
                                  bio=github_user['bio'],
                                  twitter_username=github_user['twitter_username'])
                profile.save()

            if not profile.avatar_url:
                profile.avatar_url = github_user['avatar_url']
                profile.save()

            if not token:
                token, created = Token.get_or_create(user=user, token_type='login')

            return HttpResponseRedirect(redirect_to=url + '?token=' + token.key)

        else:
            raise APIException('Error from github')
