import os, requests, sys, pytz, datetime
from django.utils import timezone
from django.db.models.expressions import RawSQL
from django.core.management.base import BaseCommand, CommandError
from django.db import models as DM
from django.db.models import Q, F
from ...models import Pipeline
from ...tasks import async_run_pipeline


class BaseSQL(object):
    template = "NOW() - INTERVAL '1 MINUTE' * %(expressions)s"


class DurationAgr(BaseSQL, DM.Aggregate):

    def __init__(self, expression, **extra):
        super(DurationAgr, self).__init__(expression, output_field=DM.DateTimeField(), **extra)


class Command(BaseCommand):
    help = 'Run pending pipelines'

    def handle(self, *args, **options):
        now = timezone.now()
        pipelines = Pipeline.objects\
                    .filter(Q(started_at__isnull=True) | Q(started_at__lte= now - F('frequency_delta_minutes')))\
                    .exclude(paused_until__isnull=False, paused_until__gte=now).values_list('slug', flat=True)

        for slug in pipelines:
            async_run_pipeline.delay(slug)

        self.stdout.write(self.style.SUCCESS(f'Enqueued {len(pipelines)} scripts for execution'))
