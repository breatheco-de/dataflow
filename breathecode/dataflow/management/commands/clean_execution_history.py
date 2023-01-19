import os, requests, sys, pytz, datetime
from django.utils import timezone
from django.db.models.expressions import RawSQL
from django.core.management.base import BaseCommand, CommandError
from django.db import models as DM
from django.db.models import Q, F
from ...models import PipelineExecution
from ...tasks import async_run_pipeline


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('pipeline', type=str)
        parser.add_argument(
            '--override',
            action='store_true',
            help='Delete and add again',
        )
        parser.add_argument('--limit',
                            action='store',
                            dest='limit',
                            type=int,
                            default=0,
                            help='How many to import')

    def handle(self, *args, **options):
        filter_by = sys.argv[2]
        if filter_by is not None:
            executions = PipelineExecution.objects.filter(pipeline__slug=filter_by).all()
            executions.delete()
        if filter_by == 'all':
            executions = PipelineExecution.objects.all()
            executions.delete()

