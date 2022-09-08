import os, ast, base64
from django.contrib import admin
from django import forms
from django.utils import timezone
from .models import Token, CredentialsGithub, UserProxy
from django.utils.html import format_html


def clear_user_password(modeladmin, request, queryset):
    for u in queryset:
        u.set_unusable_password()
        u.save()


def clean_all_tokens(modeladmin, request, queryset):
    user_ids = queryset.values_list('id', flat=True)
    count = delete_tokens(users=user_ids, status='all')


def clean_expired_tokens(modeladmin, request, queryset):
    user_ids = queryset.values_list('id', flat=True)
    count = delete_tokens(users=user_ids, status='expired')


def send_reset_password(modeladmin, request, queryset):
    reset_password(users=queryset)


@admin.register(UserProxy)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'github_login')
    actions = [clean_all_tokens, clean_expired_tokens, send_reset_password, clear_user_password]

    def get_queryset(self, request):

        self.github_callback = request.path
        self.github_callback = str(base64.urlsafe_b64encode(self.github_callback.encode('utf-8')), 'utf-8')
        return super(UserAdmin, self).get_queryset(request)

    def github_login(self, obj):
        return format_html(
            f"<a rel='noopener noreferrer' target='_blank' href='/v1/auth/github/?user={obj.id}&url={self.github_callback}'>connect github</a>"
        )


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('key', 'token_type', 'expires_at', 'user')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ['user']

    def get_readonly_fields(self, request, obj=None):
        return ['key']


@admin.register(CredentialsGithub)
class CredentialsGithubAdmin(admin.ModelAdmin):
    list_display = ('github_id', 'user_id', 'email', 'token')
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'email']
    raw_id_fields = ['user']
