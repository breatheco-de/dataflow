from django.db import models
from django.contrib.auth.models import User
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
    description = models.TextField()
    github_url = models.URLField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

class DataSource(models.Model):
    title = models.CharField(max_length=100)
    connection_string = models.CharField(max_length=250)

class Pipeline(models.Model):
    title = models.CharField(max_length=100)

    status_text = models.CharField(
        max_length=255, default=None, null=True, blank=True)
    notify_email = models.CharField(max_length=255,
                                    blank=True,
                                    default=None,
                                    null=True,
                                    help_text='Comma separated list of emails')
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    status = models.CharField(
        max_length=20, choices=STATUS, default=OPERATIONAL)

    paused = models.BooleanField(default=False)
    paused_until = models.DateTimeField(null=True,
                                        blank=True,
                                        default=None,
                                        help_text='if you want to stop checking for a period of time')

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.title


class PipelineStep(models.Model):
    title = models.CharField(max_length=100)

    status_text = models.CharField(
        max_length=255, default=None, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS, default=OPERATIONAL)

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.title