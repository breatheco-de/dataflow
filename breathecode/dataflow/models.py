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
        for pipeline in self.config['pipelines']:
            if not isinstance(pipeline, dict):
                raise Exception('Project pipelines property must be a dictionary on the YML')
            if 'slug' not in pipeline:
                raise Exception('Missing pipeline slug on the YML')
            if 'transformations' not in pipeline:
                raise Exception(f'Pipline {pipeline["name"]} is missing transformations list on the YML')
            if not isinstance(pipeline['transformations'], list):
                raise Exception('Project.pipelines[].transformations property must be a list on the YML')

        return self.config


class DataSource(models.Model):
    title = models.CharField(max_length=100)
    connection_string = models.CharField(max_length=250)


class Pipeline(models.Model):
    slug = models.SlugField()
    status_text = models.CharField(max_length=255, default=None, null=True, blank=True)
    notify_email = models.CharField(max_length=255,
                                    blank=True,
                                    default=None,
                                    null=True,
                                    help_text='Comma separated list of emails')
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=STATUS, default=OPERATIONAL)

    paused = models.BooleanField(default=False)
    paused_until = models.DateTimeField(null=True,
                                        blank=True,
                                        default=None,
                                        help_text='if you want to stop checking for a period of time')

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.title


class Transformation(models.Model):
    slug = models.SlugField()
    url = models.URLField()

    status_text = models.CharField(max_length=255, default=None, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default=OPERATIONAL)

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)

    code = models.TextField()

    last_sync_at = models.DateTimeField(blank=True, null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.title
