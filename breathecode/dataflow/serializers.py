from rest_framework import serializers
from rest_framework.exceptions import ValidationError
import serpy
from django.utils import timezone


class PipelineSerializer(serpy.Serializer):
    id = serpy.Field()
    slug = serpy.Field()


class ExecutionSerializer(serpy.Serializer):
    id = serpy.Field()
    incoming_stream = serpy.Field()
    status = serpy.Field()
    created_at = serpy.Field()
    updated_at = serpy.Field()
    started_at = serpy.Field()
    ended_at = serpy.Field()
    pipeline = PipelineSerializer()