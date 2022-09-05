from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from .models import Token


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