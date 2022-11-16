import os, logging
from urllib.parse import urlencode, parse_qs
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from .models import Pipeline, PipelineExecution
from .serializers import ExecutionSerializer
from .tasks import async_run_pipeline

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def process_stream(request, pipeline_slug):

    pipeline = Pipeline.objects.filter(slug=pipeline_slug).first()
    if pipeline is None:
        return ValidationException('Pipeline not found', status=404)

    execution = PipelineExecution(pipeline=pipeline, incoming_stream=request.data)
    execution.started_at = timezone.now()
    execution.save()  #save to get an id

    async_run_pipeline.delay(pipeline.slug, execution_id=execution.id)

    return Response(ExecutionSerializer(execution).data)
