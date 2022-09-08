from django.db import models
from django.contrib.auth.models import User
from github import Github, GithubException
from datetime import timedelta

LOADING = 'LOADING'
OPERATIONAL = 'OPERATIONAL'
MINOR = 'MINOR'
CRITICAL = 'CRITICAL'
STATUS = (
    (LOADING, 'Loading'),
    (OPERATIONAL, 'Operational'),
    (MINOR, 'Minor'),
    (CRITICAL, 'Critical'),
)


class Project(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField()
    branch_name = models.CharField(max_length=50,
                                   default='main',
                                   help_text='The branch that will be used to pull from github')
    description = models.TextField()
    github_url = models.URLField()
    config = models.JSONField(blank=True, null=True, default=None)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def get_config(self):

        if 'pipelines' not in self.config:
            raise Exception('Missing pipelines property on YML')

        if not isinstance(self.config['pipelines'], list):
            raise Exception('Project pipelines property must be a list on the YML')
        pipeline_index = 0
        for pipeline in self.config['pipelines']:
            if not isinstance(pipeline, dict):
                raise Exception('Project pipelines property must be a dictionary on the YML')
            if 'slug' not in pipeline:
                raise Exception('Missing pipeline slug on the YML')
            if 'transformations' not in pipeline:
                raise Exception(f'Pipline {pipeline["name"]} is missing transformations list on the YML')
            if not isinstance(pipeline['transformations'], list):
                raise Exception('Project.pipelines[].transformations property must be a list on the YML')

            count = len(self.config['pipelines'][pipeline_index]['transformations'])
            for index in range(count):
                self.config['pipelines'][pipeline_index]['transformations'][index] = self.config['pipelines'][
                    pipeline_index]['transformations'][index].split('.')[0]

        return self.config


class DataSource(models.Model):
    title = models.CharField(max_length=100)
    source_type = models.CharField(max_length=100)
    table_name = models.CharField(
        max_length=100,
        help_text='If source is a destination, we will automatically prepend pipeline slug to the table name')
    database = models.CharField(max_length=250,
                                help_text='Will be ignored if heroku',
                                blank=True,
                                null=True,
                                default=None)
    connection_string = models.CharField(max_length=250,
                                         blank=True,
                                         null=True,
                                         default=None,
                                         help_text='Will be ignored if Google BigQuery')

    def __str__(self):
        return f'{self.title}: {self.source_type}.{self.table_name}'


class Pipeline(models.Model):
    slug = models.SlugField()
    status_text = models.CharField(max_length=255, default=None, null=True, blank=True)
    notify_email = models.CharField(max_length=255,
                                    blank=True,
                                    default=None,
                                    null=True,
                                    help_text='Comma separated list of emails')
    source_from = models.ForeignKey(DataSource,
                                    on_delete=models.CASCADE,
                                    blank=True,
                                    null=True,
                                    default=None,
                                    related_name='pipeline_from_set')
    source_to = models.ForeignKey(DataSource,
                                  on_delete=models.CASCADE,
                                  blank=True,
                                  null=True,
                                  default=None,
                                  related_name='pipeline_to_set')
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=STATUS, default=OPERATIONAL)
    replace_destination_table = models.BooleanField(
        default=False, help_text='Will delete the table and create it again on every run')
    paused = models.BooleanField(default=False)
    paused_until = models.DateTimeField(null=True,
                                        blank=True,
                                        default=None,
                                        help_text='if you want to stop checking for a period of time')
    started_at = models.DateTimeField(null=True, blank=True, default=None)
    ended_at = models.DateTimeField(null=True, blank=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.slug


class PipelineExecution(models.Model):
    started_at = models.DateTimeField(null=True, blank=True, default=None)
    ended_at = models.DateTimeField(null=True, blank=True, default=None)
    status = models.CharField(max_length=20, choices=STATUS, default=OPERATIONAL)
    stdout = models.TextField(blank=True, null=True, default=None)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)
    log = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return f'{self.pipeline.slug} at {self.created_at}'


class Transformation(models.Model):
    slug = models.SlugField()
    url = models.URLField()

    status = models.CharField(max_length=20, choices=STATUS, default=OPERATIONAL)
    status_code = models.IntegerField(blank=True, null=True, default=None)

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)

    code = models.TextField()
    stdout = models.TextField(blank=True, null=True, default=None)

    last_sync_at = models.DateTimeField(blank=True, null=True, default=None)
    last_run = models.DateTimeField(blank=True, null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.slug
