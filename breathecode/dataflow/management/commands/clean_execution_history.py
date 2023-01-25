from django.core.management.base import BaseCommand, CommandError
from ...models import PipelineExecution


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('pipeline', type=str)

    def handle(self, *args, **options):
        pipeline_slug = sys.argv[2]
        if pipeline_slug is None or pipeline_slug == "":
            raise Exception('Missing pipeline slug')

        executions = PipelineExecution.objects.all()
        if pipeline_slug != 'all':
            executions = executions.filter(pipeline__slug=pipeline_slug)

        print(f'Deleting {len(executions)} records found in the database.')
        executions.delete()
        print('Records deleted successfully')

