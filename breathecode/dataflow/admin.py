import os, ast
from django.contrib import admin
from django import forms
from django.utils import timezone
from .models import Pipeline, PipelineStep, Project, DataSource
from django.utils.html import format_html


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'current_status')
    # actions = [run_single_script]
    list_filter = ['title']

    def current_status(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'CRITICAL': 'bg-error',
            'FATAL': 'bg-error',  # important: this status was deprecated and deleted!
            'MINOR': 'bg-warning',
        }
        return format_html(f"<span class='badge {colors[obj.status]}'>{obj.status}</span>")


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    # form = CustomForm
    list_display = ('title', 'current_status')
    # actions = [run_single_script]
    list_filter = ['status', 'project__title']

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

