import re, yaml, base64
from github import Github, GithubException
from slugify import slugify
from django.utils import timezone
from breathecode.authenticate.models import CredentialsGithub


def get_url_info(url: str):

    result = re.search(r'blob\/([\w\-]+)', url)
    branch_name = None
    if result is not None:
        branch_name = result.group(1)

    result = re.search(r'https?:\/\/github\.com\/([\w\-]+)\/([\w\-]+)\/?', url)
    if result is None:
        raise Exception('Invalid URL when looking organization: ' + url)

    org_name = result.group(1)
    repo_name = result.group(2)

    return org_name, repo_name, branch_name


def get_blob_content(repo, path_name, branch='main'):
    # first get the branch reference
    ref = repo.get_git_ref(f'heads/{branch}')
    # then get the tree
    tree = repo.get_git_tree(ref.object.sha, recursive='/' in path_name).tree
    # look for path in tree
    sha = [x.sha for x in tree if x.path == path_name]
    if not sha:
        # well, not found..
        return None
    # we have sha
    return repo.get_git_blob(sha[0])


def pull_project_from_github(project):

    credentials = CredentialsGithub.objects.filter(user__id=project.owner.id).first()
    if credentials is None:
        raise Exception(
            f'Github credentials for this user {project.owner.id} not found when sync project {project.slug}')

    org_name, repo_name, branch_name = get_url_info(project.github_url)

    g = Github(credentials.token)
    repo = g.get_repo(f'{org_name}/{repo_name}')

    yml = get_blob_content(repo, 'project.yml', branch=project.branch_name)
    if yml is None:
        raise Exception('Project.yml is empty')

    yml = base64.b64decode(yml.content.encode('utf-8')).decode('utf-8')
    project.config = yaml.safe_load(yml)

    if 'name' not in project.config:
        raise Exception('Missing project name on YML')

    config = project.get_config()
    for pipeline in config['pipelines']:
        pipelineObject = Pipeline.objects.filter(slug=pipeline['slug'], project__slug=project.slug).first()
        if pipelineObject is None:
            pipelineObject = Pipeline(
                slug=pipeline['slug'],
                project=project,
            )
            pipelineObject.save()

        for t in pipeline['transformations']:
            trans_url = f'transformations/{pipeline["slug"]}/{t.split(".")[0]}.py'
            python_code = get_blob_content(repo, trans_url, branch=project.branch_name)
            if python_code is None:
                raise Exception(
                    f'Transformation file transformations/{pipeline["slug"]}/{t.split(".")[0]}.py not found')

            transObject = Transformation.objects.filter(slug=t.split('.')[0],
                                                        pipeline__slug=pipelineObject.slug).first()
            if transObject is None:
                trans = Transformation(
                    slug=t.split('.')[0],
                    pipeline=pipelineObject,
                    url=trans_url,
                )
            transObject.code = yml.content
            transObject.last_sync_at = timezone.now()
            transObject.save()

    project.save()
