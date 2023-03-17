import os, ast, logging, traceback
from django.contrib import admin
from django import forms
from breathecode.utils import getLogger
from django.utils import timezone
from django.http import HttpResponse
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

def download_sample_data(self, request, queryset):

    sources = queryset.all()
    if sources.count() != 1:
        messages.add_message(request, messages.ERROR, "Please choose one source to download data from")
        return None

    source = sources[0]
    driver = source.get_source()
    df = driver.get_dataframe_from_table(source.table_name)
    offset = 0
    rows = 100
    
    data = df.iloc[offset:offset + rows]
    csv_data = data.to_csv(index=False)
    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="' + str(source.slug) + '.csv"'
    return response


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
    actions = [download_sample_data]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id','slug', 'description', 'owner', 'last_pull')
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


def remove_pause(modeladmin, request, queryset):
    queryset.update(paused_until=None)


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('slug', 'sources', 'source_to', 'current_status')
    actions = [execute_async, pause_for_one_day, pause_for_thirty_days, remove_pause]
    list_filter = ['status', 'project__title']

    # actions=[pull_github_project]

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'LOADING': 'bg-warning',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
            'ABORTED': 'bg-error',
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
    list_display = ('id', 'slug', 'order', 'current_status', 'pipeline', 'last_run', 'last_sync_at', 'script')
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
            'ABORTED': 'bg-error',
        }
        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")

    def script(self, obj):
        return format_html(f"<a target='_blank' href='/v1/transformation/{obj.slug}/code'>view code</span>")



def backup_buffer_to_gcp(modeladmin, request, queryset):
    executions = queryset.all()
    for e in executions:
        try:
            position = e.pipeline.transformation_set.filter(status='OPERATIONAL').count()
            if position > 0:
                e.backup_buffer(position-1)
        except Exception as e:
            logger.exception(e)

def abort_execution(modeladmin, request, queryset):
    queryset.update(status='ABORTED')

@admin.register(PipelineExecution)
class PipelineExecutionAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('id', 'pipeline', 'current_status', 'started_at', 'buffer')
    list_filter = ['status', 'pipeline__slug', 'pipeline__project__slug']
    actions = [backup_buffer_to_gcp, abort_execution]

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'LOADING': 'bg-warning',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
            'ABORTED': 'bg-error',
        }
        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")

    def buffer(self, obj):
        return format_html(
            f"<a href='/v1/execution/{obj.id}/buffer?position=0&rows=500&offset=0'>download buffer</span>"
        )
