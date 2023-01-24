from django.core.management.base import BaseCommand, CommandError
from ...models import PipelineExecution


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('pipeline', type=str)

    def handle(self, *args, **options):
        pipeline_slug = sys.argv[2]
        if pipeline__slug == None:
            raise Exception('Missing pipeline slug')
        if pipeline_slug == 'all':
            executions = PipelineExecution.objects.all()
            if len(executions) == 0:
                print('No matching records found in the database.')
            else:
                executions.delete()
                print('Records deleted successfully')
        else:
            executions = PipelineExecution.objects.filter(pipeline__slug=pipeline_slug).all()
            if len(executions) == 0:
                print('No matching records found in the database.')
            else:
                executions.delete()
                print('Records deleted successfully')
        

