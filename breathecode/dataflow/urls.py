from django.contrib import admin
from django.urls import path, include
from .views import process_stream

app_name = 'dataflow'
urlpatterns = [
    path('stream/<slug:pipeline_slug>', process_stream),
]
