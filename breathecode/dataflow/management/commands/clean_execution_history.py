from django.core.management.base import BaseCommand, CommandError
from ...models import PipelineExecution
import sys
from datetime import datetime, timedelta
from django.utils import timezone
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--pipeline', type=str)
        parser.add_argument('--days_old', type=int, help='Delete executions older than the specified number of days')

    def handle(self, *args, **options):
        pipeline_slug = options.get('pipeline')
        days_old = options.get('days_old')

        executions = PipelineExecution.objects.all()
        if pipeline_slug:
            executions = executions.filter(pipeline__slug=pipeline_slug)
        if days_old:
            date_limit = timezone.make_aware(datetime.now() - timedelta(days=days_old))
            executions = executions.filter(started_at__lt=date_limit)

        print(f'Deleting {len(executions)} records found in the database.')
        executions.delete()
        print('Records deleted successfully')

# ----USAGE----

# --To delete all the records:
# $ python manage.py clean_execution_history

# --To delete all the records of a specific pipeline:
# $ python manage.py clean_execution_history --pipeline=<pipeline_slug>

# --To delete all the records older than a specified number of days:
# $ python manage.py clean_execution_history --days_old=<days_old>

# --To delete all the records from a pipeline an older than a specified number of days:
# $ python manage.py clean_execution_history --pipeline=<pipeline_slug> --days_old=<days_old>

