from django.contrib import admin
from django.urls import path, include
from .views import process_stream, get_execution_buffer

app_name = 'dataflow'
urlpatterns = [
    path('stream/<slug:pipeline_slug>', process_stream),
    path('execution/<int:execution_id>/buffer', get_execution_buffer),
]
