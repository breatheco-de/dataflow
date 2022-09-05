from django.contrib import admin
from django.urls import path, include
from .views import get_token_info, TemporalTokenView

app_name = 'authenticate'
urlpatterns = [
    path('token/me', TemporalTokenView.as_view(), name='token'),
    path('token/<str:token>', get_token_info, name='token'),  # get token information
]
