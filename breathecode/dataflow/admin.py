import os, ast, logging, traceback
from django.contrib import admin
from django import forms
from breathecode.utils import getLogger
from django.utils import timezone
from django.contrib import messages
from .models import Pipeline, Transformation, Project, DataSource, PipelineExecution
from .actions import pull_project_from_github
from .tasks import async_run_pipeline
from django.utils.html import format_html
from .utils import PipelineException

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
    list_display = ('slug', 'title', 'source_type', 'table_name')
    # actions = [run_single_script]
    list_filter = ['title']
    # actions = [pull_github_project]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('slug', 'description', 'owner')
    # actions = [run_single_script]
    list_filter = ['slug']
    actions = [pull_github_project]


def execute_async(modeladmin, request, queryset):
    pipelines = queryset.all()

    for p in pipelines:
        try:
            async_run_pipeline.delay(p.slug)
        except Exception as e:
            logger.exception(e)
            messages.add_message(request, messages.ERROR, str(e))


def pause_for_one_day(modeladmin, request, queryset):
    queryset.update(paused_until=timezone.now() + timezone.timedelta(days=1))


def pause_for_thirty_days(modeladmin, request, queryset):
    queryset.update(paused_until=timezone.now() + timezone.timedelta(days=30))


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('slug', 'sources', 'source_to', 'current_status')
    actions = [execute_async, pause_for_one_day, pause_for_thirty_days]
    list_filter = ['status', 'project__title']

    # actions=[pull_github_project]

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'LOADING': 'bg-warning',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
        }
        now = timezone.now()
        if obj.paused_until is not None and obj.paused_until > now:
            return format_html(f"<span class='badge bc-warning'> ⏸ PAUSED</span>")

        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")

    def sources(self, obj):
        return ', '.join([str(source.slug) + f' ({source.id})' for source in obj.source_from.all()])


@admin.register(Transformation)
class TransformationAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('id', 'slug', 'order', 'current_status', 'pipeline', 'last_run', 'last_sync_at')
    # actions = [run_single_script]
    list_filter = ['status', 'pipeline__slug', 'pipeline__project__slug']

    # actions=[pull_github_project]

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'LOADING': 'bg-warning',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
        }
        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")


@admin.register(PipelineExecution)
class PipelineExecutionAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('id', 'pipeline', 'current_status', 'started_at')
    list_filter = ['status', 'pipeline__slug', 'pipeline__project__slug']

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'LOADING': 'bg-warning',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
        }
        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")
