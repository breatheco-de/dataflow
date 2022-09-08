from django.contrib import admin
from django.urls import path, include
from .views import get_token_info, TemporalTokenView, get_github_token, save_github_token

app_name = 'authenticate'
urlpatterns = [
    path('token/me', TemporalTokenView.as_view(), name='token'),
    path('token/<str:token>', get_token_info, name='token'),  # get token information
    path('github/', get_github_token, name='github'),
    path('github/<str:token>', get_github_token, name='github_token'),
    path('github/callback/', save_github_token, name='github_callback'),
]
