import os, logging
from urllib.parse import urlencode, parse_qs
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from .models import Pipeline, PipelineExecution
from breathecode.utils import ValidationException
from .serializers import ExecutionSerializer
from .tasks import async_run_pipeline
import pandas as pd

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
def get_execution_buffer(request, execution_id=None):

    execution = PipelineExecution.objects.filter(id=execution_id).first()
    if execution is None:
        raise ValidationException('Pipeline Execution not found', code=404)

    position = int(request.GET.get('position', 0))
    offset = int(request.GET.get('offset', 0))
    rows = int(request.GET.get('rows', 500))

    try:

        buffer_url = execution.buffer_url(position)
        if not os.path.isfile(buffer_url):
            raise ValidationException("Execution buffer not found for position %s" % position)

        df = pd.read_csv(buffer_url)
        data = df.iloc[offset:offset+rows]
        csv_data = data.to_csv(index=False)
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="'+str(execution)+'.csv"'
        return response
    except Exception as e:
        logger.error(e)
        raise ValidationException(str(e))


