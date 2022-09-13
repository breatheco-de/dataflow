import os, ast, logging
from django.contrib import admin
from django import forms
from breathecode.utils import getLogger
from django.utils import timezone
from django.contrib import messages
from .models import Pipeline, Transformation, Project, DataSource
from .actions import pull_project_from_github, run_pipeline
from django.utils.html import format_html

logger = getLogger(__name__)


def pull_github_project(modeladmin, request, queryset):
    projects = queryset.all()

    for p in projects:
        try:
            pull_project_from_github(p)
        except Exception as e:
            logger.exception(e)
            messages.add_message(request, messages.ERROR, str(e))


class DataSourceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(DataSourceForm, self).__init__(*args, **kwargs)
        self.fields['source_type'] = forms.ChoiceField(
            choices=[('heroku', 'Heroku'), ('bigquery', 'BigQuery'), ('csv', 'CSV File on datastore')])


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    form = DataSourceForm
    list_display = ('title', 'source_type', 'table_name')
    # actions = [run_single_script]
    list_filter = ['title']
    # actions = [pull_github_project]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('slug', 'description', 'owner')
    # actions = [run_single_script]
    list_filter = ['slug']
    actions = [pull_github_project]


def execute_now(modeladmin, request, queryset):
    pipelines = queryset.all()

    for p in pipelines:
        try:
            run_pipeline(p)
        except Exception as e:
            logger.exception(e)
            messages.add_message(request, messages.ERROR, str(e))


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('slug', 'source_from', 'source_to', 'current_status')
    actions = [execute_now]
    list_filter = ['status', 'project__title']

    # actions=[pull_github_project]

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
        }
        now = timezone.now()
        if obj.paused_until is not None and obj.paused_until > now:
            return format_html(f"<span class='badge bc-warning'> ⏸ PAUSED</span>")

        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")


@admin.register(Transformation)
class TransformationAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('slug', 'current_status', 'pipeline', 'last_run', 'last_sync_at')
    # actions = [run_single_script]
    list_filter = ['status', 'pipeline__slug', 'pipeline__project__slug']

    # actions=[pull_github_project]

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
        }
        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")
