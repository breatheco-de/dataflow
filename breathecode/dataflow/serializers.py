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



class ProjectSerializer(serpy.Serializer):
    id = serpy.Field()
    title = serpy.Field()
    slug = serpy.Field()
    branch_name = serpy.Field()
    description = serpy.Field()
    github_url = serpy.Field()
    config = serpy.Field()
    owner_id = serpy.Field()

    def to_value(self, instance):
        data = super().to_value(instance)
        data['owner_id'] = instance.owner.id
        return data


class BigPipelineSerializer(serpy.Serializer):
    id = serpy.Field()
    slug = serpy.Field()
    color = serpy.MethodField()
    status = serpy.Field()
    frequency_delta_minutes = serpy.Field()
    started_at = serpy.Field()
    ended_at = serpy.Field()
    created_at = serpy.Field()
    updated_at = serpy.Field()

    def get_color(self, obj):
        colors = {
            'OPERATIONAL': 'bg-success',
            'LOADING':'bg-minor',
            'MINOR' :'bg-minor',
            'CRITICAL' : 'bg-danger'
        }
        return colors[obj.status]