import os, ast
from django.contrib import admin
from django import forms
from django.utils import timezone
from .models import Token
from django.utils.html import format_html

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('key', 'token_type', 'expires_at', 'user')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ['user']

    def get_readonly_fields(self, request, obj=None):
        return ['key']