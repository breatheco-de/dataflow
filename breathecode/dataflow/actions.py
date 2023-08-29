import re
from github import Github, GithubException
from slugify import slugify
from django.utils import timezone
from breathecode.authenticate.models import CredentialsGithub
from google.cloud.exceptions import NotFound
from breathecode.services.google_cloud.bigquery import BigQuery
from .models import PipelineExecution, Pipeline, Project, Transformation, DataSource
from .utils import PipelineException, HerokuDB, RemoteCSV
from .tasks import async_run_transformation


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
    project.save_config(yml.content)

    if 'name' not in project.config:
        raise Exception('Missing project name on YML')

    config = project.get_config()
    for pipeline in config['pipelines']:
        pipelineObject = Pipeline.objects.filter(slug=pipeline['slug'], project__slug=project.slug).first()

        if 'destination' not in pipeline or pipeline['destination'] == "" or not isinstance(pipeline['destination'], str):
            raise Exception(
                f'Pipeline is has invalid or missing destination property with the slug of the DataSource that will be used to save the pipeline output'
            )
        destination = DataSource.objects.filter(slug=pipeline['destination'].strip()).first()
        if destination is None:
            raise Exception(
                f"Destination DataSource with slug {pipeline['destination']} not found on the database but was specified on the pipeline YML"
            )

        if pipelineObject is not None:
            other_pipeline_using_same_destination = Pipeline.objects.filter(source_to=destination).first()
            if other_pipeline_using_same_destination is not None and other_pipeline_using_same_destination.id != pipelineObject.id:
                raise Exception(
                    f"Another pipeline is already using destination datasource {destination.slug}"
                )
        
        if pipelineObject is None:
            pipelineObject = Pipeline(
                slug=pipeline['slug'],
                project=project,
            )
            pipelineObject.save()

        Transformation.objects.filter(pipeline__slug=pipelineObject.slug).exclude(
            slug__in=pipeline['transformations']).delete()

        if 'sources' not in pipeline:
            raise Exception(
                f'Pipeline is missing sources property with the list and order on which the sources will be added to the transformations'
            )
        pipelineObject.source_from.clear()

        for s in pipeline['sources']:
            source = DataSource.objects.filter(slug=s).first()
            if source is None:
                raise Exception(
                    f"Source with slug '{s}' not found on the database but was specified on the YML")

            pipelineObject.source_from.add(source)
            
        pipelineObject.source_to = destination
        pipelineObject.save()

        order = 0
        for t in pipeline['transformations']:
            order += 1
            trans_url = f'pipelines/{pipeline["slug"]}/{t.split(".")[0]}.py'
            python_code = get_blob_content(repo, trans_url, branch=project.branch_name)
            if python_code is None:
                raise Exception(
                    f'Transformation file pipelines/{pipeline["slug"]}/{t.split(".")[0]}.py not found')

            transObject = Transformation.objects.filter(slug=t.split('.')[0],
                                                        pipeline__slug=pipelineObject.slug).first()
            if transObject is None:
                transObject = Transformation(
                    slug=t.split('.')[0],
                    pipeline=pipelineObject,
                    url=trans_url,
                )
            transObject.order = order
            transObject.code = python_code.content
            transObject.last_sync_at = timezone.now()
            transObject.save()
    project.last_pull = timezone.now()
    project.save()
