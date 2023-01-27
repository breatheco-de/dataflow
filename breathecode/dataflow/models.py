import base64, yaml, os, traceback
import pandas as pd
from django.db import models
from django.contrib.auth.models import User
from github import Github, GithubException
from datetime import timedelta
from .utils import HerokuDB, RemoteCSV
from breathecode.services.google_cloud.bigquery import BigQuery

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

    def __str__(self):
        return self.title

    def get_config(self, pipeline_slug=None):

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
            if 'sources' not in pipeline:
                raise Exception('Missing sources list of slugs on the YML')
            if 'transformations' not in pipeline:
                raise Exception(f'Pipline {pipeline["name"]} is missing transformations list on the YML')
            if not isinstance(pipeline['transformations'], list):
                raise Exception('Project.pipelines[].transformations property must be a list on the YML')

            count = len(self.config['pipelines'][pipeline_index]['transformations'])
            for index in range(count):
                self.config['pipelines'][pipeline_index]['transformations'][index] = self.config['pipelines'][
                    pipeline_index]['transformations'][index].split('.')[0]

        if pipeline_slug is not None:
            for p in self.config['pipelines']:
                if p['slug'] == pipeline_slug:
                    return p
            raise Exception(f'Pipeline {pipeline_slug} does not exist on the YML')

        return self.config

    def save_config(self, yml):
        yml_content = base64.b64decode(yml.encode('utf-8')).decode('utf-8')
        self.config = yaml.safe_load(yml_content)


class DataSource(models.Model):
    slug = models.SlugField(null=True, default=None)
    title = models.CharField(max_length=100)
    source_type = models.CharField(max_length=100)
    quoted_newlines = models.BooleanField(default=True)
    table_name = models.TextField(
        null=True,
        blank=True,
        default=None,
        help_text=
        'Ignored for CSV. You can write a SELECT query statement, but for Heroku, SQL or Big Query only.')
    database = models.CharField(max_length=250,
                                help_text='Ignored if Heroku or CSV.',
                                blank=True,
                                null=True,
                                default=None)
    connection_string = models.CharField(max_length=250,
                                         blank=True,
                                         null=True,
                                         default=None,
                                         help_text='Ignored if Google BigQuery. File path if CSV.')

    def __str__(self):
        return f'{self.title}: {self.source_type}.{self.table_name}'

    def get_source(self):
        if self.source_type == 'bigquery':
            return BigQuery(dataset=self.database)
        if self.source_type == 'heroku':
            return HerokuDB(connection_string=self.connection_string)
        if self.source_type == 'csv':
            return RemoteCSV(connection_string=self.connection_string)

        raise Exception(f'Invalid pipeline source type {self.source_type}')


class Pipeline(models.Model):
    slug = models.SlugField()
    status_text = models.CharField(max_length=255, default=None, null=True, blank=True)
    notify_email = models.CharField(max_length=255,
                                    blank=True,
                                    default=None,
                                    null=True,
                                    help_text='Comma separated list of emails')
    source_from = models.ManyToManyField(DataSource, blank=True, related_name='pipeline_from_set')
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

    paused_until = models.DateTimeField(null=True,
                                        blank=True,
                                        default=None,
                                        help_text='if you want to stop checking for a period of time')
    frequency_delta_minutes = models.DurationField(
        default=timedelta(minutes=30),
        help_text='How long to wait for the next execution, defaults to 30 minutes')
    started_at = models.DateTimeField(null=True, blank=True, default=None)
    ended_at = models.DateTimeField(null=True, blank=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.slug

    def destination_table_name(self):
        if self.source_to is None:
            raise Exception(f'Pipeline {self.slug} is missing source_to (destination)')

        if self.source_to.source_type == 'csv' and self.source_to.connection_string is not None:
            return self.source_to.connection_string

        return self.source_to.table_name


PENDING = 'PENDING'
DONE = 'DONE'
ERROR = 'ERROR'
STREAM_STATUS = (
    (PENDING, 'Pending'),
    (DONE, 'Done'),
    (ERROR, 'Error'),
)


class PipelineExecution(models.Model):
    started_at = models.DateTimeField(null=True, blank=True, default=None)
    ended_at = models.DateTimeField(null=True, blank=True, default=None)
    status = models.CharField(max_length=20, choices=STATUS, default=LOADING)
    stdout = models.TextField(blank=True, null=True, default='')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)
    log = models.JSONField(blank=True, null=True, default=None)

    incoming_stream = models.JSONField(blank=True,
                                       null=True,
                                       default=None,
                                       help_text='If set, the pipeline will be treated like a stream')

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return f'{self.pipeline.slug} at {self.created_at}'

    def log_exception(self, e):
        self.stdout += '\n'.join(traceback.format_exception(None, e, e.__traceback__))

    def buffer_url(self, position=0):
        return './buffer/' + str(self.id) + self.pipeline.slug + f'_buffer{position}.csv'

    def get_buffer_df(self, position=0):
        return pd.read_csv(self.buffer_url(position))

    def save_buffer_df(self, df, position=0):
        if not os.path.exists('./buffer'):
            raise Exception('Directory "buffer" does not exists')
        result = df.to_csv(self.buffer_url(position), index=False)
        print('saved buffer')

    def backup_buffer(self, position=0):
        from breathecode.services.google_cloud.storage import Storage

        storage = Storage()
        bucket_name = os.environ.get('GOOGLE_BUCKET_NAME', None)

        buffer_url = self.buffer_url(position)
        if not os.path.isfile(buffer_url):
            raise ValidationException("Execution buffer not found for position %s" % position)

        if not os.path.exists('./buffer'):
            raise Exception('Directory "buffer" does not exists')

        backup_path = f'buffer/{self.pipeline.slug}.csv'
        print('Saving to ', bucket_name, backup_path)

        file = storage.file(bucket_name, backup_path)
        file.upload(from_filename=buffer_url)

        return True


class Transformation(models.Model):
    slug = models.SlugField()
    url = models.URLField()

    status = models.CharField(max_length=20, choices=STATUS, default=OPERATIONAL)
    status_code = models.IntegerField(blank=True, null=True, default=None)

    order = models.IntegerField(blank=True,
                                null=True,
                                default=None,
                                help_text='Order in which it will be executed in the pipeline')

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)

    code = models.TextField()
    stdout = models.TextField(blank=True, null=True, default='')

    last_sync_at = models.DateTimeField(blank=True, null=True, default=None)
    last_run = models.DateTimeField(blank=True, null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.slug

    def get_code(self):
        if self.code is None:
            return None
        else:
            return base64.b64decode(self.code.encode('utf-8')).decode('utf-8')

    def log_exception(self, e):
        self.stdout += '\n'.join(traceback.format_exception(None, e, e.__traceback__))
