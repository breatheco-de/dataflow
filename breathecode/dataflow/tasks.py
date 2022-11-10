import logging, sys, traceback
from django.utils import timezone
from celery import shared_task, Task
from google.cloud.exceptions import NotFound
from .models import Transformation, PipelineExecution, Pipeline

# Get an instance of a logger
logger = logging.getLogger(__name__)


class BaseTaskWithRetry(Task):
    autoretry_for = (Exception, )
    #                                           seconds
    retry_kwargs = {'max_retries': 5, 'countdown': 60 * 5}
    retry_backoff = True


def run_transformation(transformation, execution):

    from io import StringIO
    import contextlib

    @contextlib.contextmanager
    def stdoutIO(stdout=None):
        old = sys.stdout
        if stdout is None:
            stdout = StringIO()
        sys.stdout = stdout
        yield stdout
        sys.stdout = old

    content = transformation.get_code()
    if content is None:
        transformation.status = 'CRITICAL'
        transformation.stdout = f'Script not found or its body is empty: {transformation.slug}'
        transformation.save()
        return False
    else:
        content = 'import inspect\nimport pandas as pd\n' + content + '\n'

    with stdoutIO() as s:
        try:
            if transformation.pipeline is None:
                raise Exception(f'Transformation {transformation.slug} does not belong to any pipeline')

            input_vars = {}

            sources = transformation.pipeline.source_from.all()
            content += 'dfs = [] \n'
            for position in range(len(sources)):
                content += f"dfs.append(pd.read_csv('{execution.buffer_url(position)}')) \n"

            content += f"""
print('Starting {transformation.slug}: with '+str(len(dfs))+' dataframes -> '+str(dfs[0].shape))

args_spect = inspect.getfullargspec(run)
output = run(*dfs[:len(args_spect.args)])
print('Ended transformation {transformation.slug}: output -> '+str(output.shape))
output.to_csv('{execution.buffer_url()}', index=False)\n
"""
            exec(content, input_vars)
            transformation.status_code = 0
            transformation.status = 'OPERATIONAL'
            transformation.stdout = s.getvalue()

        except Exception as e:
            transformation.log_exception(e)
            transformation.status_code = 1
            transformation.status = 'CRITICAL'

    transformation.last_run = timezone.now()
    transformation.save()

    return transformation


@shared_task(bind=True, base=BaseTaskWithRetry)
def async_run_transformation(self, execution_id, transformations):
    logger.debug(f'Starting async_run_transformation with {len(transformations)} transformations pending')

    execution = PipelineExecution.objects.filter(id=execution_id).first()
    if execution is None:
        raise Exception(f'Execution with id {execution_id} not found')
    pipeline = execution.pipeline

    if len(transformations) == 0:
        return True

    next = transformations.pop()
    t = Transformation.objects.filter(pipeline__slug=pipeline.slug, slug=next).first()
    t = run_transformation(t, execution)

    # update pipeline
    pipeline.status = t.status
    pipeline.ended_at = timezone.now()

    # update execution
    execution.stdout += t.stdout
    execution.status = t.status
    execution.ended_at = timezone.now()

    if len(transformations) == 0 and t.status == 'OPERATIONAL':
        # no more transformations to apply, save in the database
        logger.debug(f'No more transformations to apply for execution {execution.id}, saving into datasource')
        try:
            df = execution.get_buffer_df()
            TO_DB = t.pipeline.source_to.get_source()
            TO_DB.save_dataframe_to_table(df,
                                          pipeline.destination_table_name(),
                                          replace=pipeline.replace_destination_table,
                                          quoted_newlines=pipeline.source_to.quoted_newlines)
            pipeline.status = 'OPERATIONAL'
            execution.status = 'OPERATIONAL'
            execution.stdout += f'Saved to database {pipeline.source_to.title}'

        except NotFound as e:
            msg = f'Dataset table not found for {pipeline.source_to.source_type}.{pipeline.source_to.database} -> table: {pipeline.source_to.table_name}'
            pipeline.status = 'CRITICAL'

            execution.stdout += msg
            execution.status = 'CRITICAL'

        except Exception as e:
            pipeline.status = 'CRITICAL'
            execution.stdout += execution.log_exception(e)
            execution.status = 'CRITICAL'

    elif len(transformations) > 0 and t.status == 'OPERATIONAL':
        async_run_transformation.delay(execution_id, transformations)

    pipeline.save()
    execution.save()

    return True


@shared_task(bind=True, base=BaseTaskWithRetry)
def async_run_pipeline(self, pipeline_slug):

    pipeline = Pipeline.objects.filter(slug=pipeline_slug).first()
    if pipeline is None:
        raise Exception(f'Pipeline {pipeline_slug} not found')

    execution = PipelineExecution(pipeline=pipeline, status='LOADING')
    execution.started_at = timezone.now()
    execution.save()  #save to get an id

    pipeline.started_at = timezone.now()
    execution.save()

    try:
        if pipeline.source_from.count() == 0 or pipeline.source_to is None:
            raise Exception(f'Pipeline {pipeline.slug} does not have both sources defined')

        # Reset transformation status
        Transformation.objects.filter(pipeline__slug=pipeline.slug).update(status='LOADING')

        pipe = pipeline.project.get_config(pipeline.slug)
        for source_from in pipeline.source_from.all():
            FROM_DB = source_from.get_source()
            df = FROM_DB.get_dataframe_from_table(source_from.table_name)
            execution.save_buffer_df(df, position=pipe['sources'].index(source_from.slug))

        # get transformations queue
        transformations = list(
            Transformation.objects.filter(pipeline__slug=pipeline.slug).order_by('-order').all())
        async_run_transformation.delay(execution.id, [t.slug for t in transformations])

    except NotFound as e:
        execution.stdout += f'Dataset table not found for {pipeline.source_from.source_type}.{pipeline.source_from.database} -> table: {pipeline.source_from.table_name}'
        execution.status = 'CRITICAL'
    except Exception as e:
        execution.log_exception(e)
        execution.status = 'CRITICAL'

    pipeline.status = execution.status
    execution.save()
    pipeline.save()
    return True
