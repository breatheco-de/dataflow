import re, yaml, base64, sys
from github import Github, GithubException
from slugify import slugify
from django.utils import timezone
from breathecode.authenticate.models import CredentialsGithub
from google.cloud.exceptions import NotFound
from breathecode.services.google_cloud.bigquery import BigQuery
from .models import PipelineExecution, Pipeline, Project, Transformation
from .utils import HerokuDB


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

    yml_content = base64.b64decode(yml.content.encode('utf-8')).decode('utf-8')
    project.config = yaml.safe_load(yml_content)

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

        Transformation.objects.filter(pipeline__slug=pipelineObject.slug).exclude(
            slug__in=pipeline['transformations']).delete()
        for t in pipeline['transformations']:
            trans_url = f'transformations/{pipeline["slug"]}/{t.split(".")[0]}.py'
            python_code = get_blob_content(repo, trans_url, branch=project.branch_name)
            if python_code is None:
                raise Exception(
                    f'Transformation file transformations/{pipeline["slug"]}/{t.split(".")[0]}.py not found')

            transObject = Transformation.objects.filter(slug=t.split('.')[0],
                                                        pipeline__slug=pipelineObject.slug).first()
            if transObject is None:
                transObject = Transformation(
                    slug=t.split('.')[0],
                    pipeline=pipelineObject,
                    url=trans_url,
                )
            transObject.code = yml.content
            transObject.last_sync_at = timezone.now()
            transObject.save()

    project.save()


def get_source(source):
    if source.source_type == 'bigquery':
        return BigQuery(dataset=source.database)
    if source.source_type == 'heroku':
        return HerokuDB(connection_string=source.connection_string)

    raise Exception(f'Invalid pipeline source type {source.source_type}')


def run_pipeline(pipeline):

    if pipeline.source_from is None or pipeline.source_to is None:
        raise Exception(f'Pipeline {pipeline.slug} does not have both sources defined')

    FROM_DB = get_source(pipeline.source_from)
    TO_DB = get_source(pipeline.source_to)

    table_name = pipeline.slug + '__' + pipeline.source_to.table_name
    pipeline.started_at = timezone.now()
    transformations = Transformation.objects.filter(pipeline__slug=pipeline.slug)
    df = None
    try:
        df = FROM_DB.get_dataframe_from_table(pipeline.source_from.table_name)
    except NotFound as e:
        raise Exception(
            f'Dataset table not found for {pipeline.source_from.source_type}.{pipeline.source_from.database} -> table: {pipeline.source_from.table_name}'
        )

    for t in transformations:
        df = run_transformation(t, df)
        print(df.shape)

    try:
        TO_DB.save_dataframe_to_table(df, table_name, replace=pipeline.replace_destination_table)
    except NotFound as e:
        raise Exception(
            f'Dataset table not found for {pipeline.source_to.source_type}.{pipeline.source_to.database} -> table: {table_name}'
        )

    pipeline.ended_at = timezone.now()
    pipeline.save()


def run_transformation(transformation, dataframe=None):

    from io import StringIO
    import contextlib

    @contextlib.contextmanager
    def stdoutIO(stdout=None):
        old = sys.stdout
        if stdout is None:
            stdout = StringIO()
        sys.stdout = stdout
        yield stdout
        sys.stdout = old

    if transformation.code is None:
        raise Exception(f'Script not found or its body is empty: {transformation.slug}')

    content = base64.b64decode(transformation.code.encode('utf-8')).decode('utf-8')
    if content:
        with stdoutIO() as s:
            try:
                if transformation.pipeline is None:
                    raise Exception(f'Transformation {transformation.slug} does not belong to any pipeline')

                content + '\nrun(_df)\n'
                dataframe = eval(content, {
                    '_df': dataframe,
                }, local)
                transformation.status_code = 0
                transformation.status = 'OPERATIONAL'
                transformation.stdout = s.getvalue()

            except Exception as e:
                import traceback
                transformation.stdout = ''.join(traceback.format_exception(None, e, e.__traceback__))
                transformation.status_code = 1
                transformation.status = 'CRITICAL'

        transformation.last_run = timezone.now()
        transformation.save()

        return dataframe

    return content is not None and transformation.status_code == 0
