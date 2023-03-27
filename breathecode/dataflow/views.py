import os, logging
import csv
from urllib.parse import urlencode, parse_qs
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from .models import Pipeline, PipelineExecution, Transformation, Project
from breathecode.utils import ValidationException
from .serializers import ExecutionSerializer, PipelineSerializer, BigPipelineSerializer, ProjectSerializer
from .tasks import async_run_pipeline
import pandas as pd
from django.http import JsonResponse
logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def process_stream(request, pipeline_slug):

    pipeline = Pipeline.objects.filter(slug=pipeline_slug).first()
    if pipeline is None:
        raise ValidationException('Pipeline not found', code=404)

    execution = PipelineExecution(pipeline=pipeline, incoming_stream=request.data)
    execution.started_at = timezone.now()
    execution.save()  #save to get an id

    async_run_pipeline.delay(pipeline.slug, execution_id=execution.id)

    return Response(ExecutionSerializer(execution).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_transformation_code(request, transformation_slug):

    transformation = Transformation.objects.filter(slug=transformation_slug).first()
    if transformation is None:
        raise ValidationException('Transformation not found', code=404)

    return render(
        request, 'transformation.html', {
            'code': transformation.get_code(),
            'pipeline': transformation.pipeline.slug,
            'slug': transformation.slug,
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def run_project(request, project_id):

    pipelines = Pipeline.objects.filter(project__id=project_id)
    for p in pipelines:
        try:
            async_run_pipeline.delay(p.slug)
        except Exception as e:
            raise ValidationException(str(e))
    
    return Response(PipelineSerializer(pipelines, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_execution_buffer(request, execution_id=None):

    execution = PipelineExecution.objects.filter(id=execution_id).first()
    if execution is None:
        raise ValidationException('Pipeline Execution not found', code=404)

    position = int(request.GET.get('position', 0))
    offset = int(request.GET.get('offset', 0))
    rows = int(request.GET.get('rows', 500))

    try:

        stream = execution.get_buffer_backup()
        response = StreamingHttpResponse(stream.all(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="' + str(execution.pipeline.slug) + '.csv"'
        return response
    except Exception as e:
        logger.error(e)
        raise ValidationException(str(e))


@api_view(['GET'])
@permission_classes([AllowAny])
def get_project_details(request, project_id):
    project = Project.objects.filter(id=project_id).first()
    if project is None:
        raise ValidationException('Project not found', code=404)

    project_serializer = ProjectSerializer(project)
    serialized_data = {
        "project": project_serializer.data,
    }

    return render(request, 'project.html', serialized_data)