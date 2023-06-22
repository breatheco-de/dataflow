import logging, sys, traceback, json, time
import psutil
from django.utils import timezone
from celery import shared_task, Task
from google.cloud.exceptions import NotFound
from .models import Transformation, PipelineExecution, Pipeline

# Get an instance of a logger
logger = logging.getLogger(__name__)


class RetryException(Exception):
    pass


class BaseTaskWithRetry(Task):
    autoretry_for = (RetryException, )
    #                                              15 minutes retry
    retry_kwargs = {'max_retries': 2, 'countdown': 60 * 15}
    retry_backoff = True
    
    start_time = time.time()
    start_memory = psutil.virtual_memory().used

    def __init__(self):
        self.start_time = time.time()
        self.start_memory = psutil.virtual_memory().used

    def log_time_and_memory(self):
        elapsed_time = time.time() - self.start_time
        current_memory = psutil.virtual_memory().used
        memory_diff = current_memory - self.start_memory
        logger.debug(f"Elapsed time: {elapsed_time}s, Memory used: {memory_diff / (1024.0 ** 2)} MB")

def run_transformation(transformation, execution):

    logger.debug(f"Running transformation {transformation.slug}")
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
        logger.debug(f"Added stdoutIO to collect log buffers from transformation {transformation.slug}")

    content = transformation.get_code()
    if content is None:
        transformation.status = 'CRITICAL'
        transformation.stdout = f'Script not found or its body is empty: {transformation.slug}'
        transformation.save()
        return False
    else:
        logger.debug(
            f"Transformation {transformation.slug} code looks OK with status {transformation.status}")
        content = f'import inspect, json\nimport pandas as pd\nprint("Preparing code for the next transformation: {transformation.slug}")\n' + content + '\n'
        logger.debug(f"Pre-prended imports to transformation code")

    with stdoutIO() as s:
        try:
            if transformation.pipeline is None:
                raise Exception(f'Transformation {transformation.slug} does not belong to any pipeline')

            input_vars = {}

            sources = transformation.pipeline.source_from.all()
            logger.debug(f"Gathering sources for {transformation.status}")
            content += 'dfs = [] \nkwargs = {}\n'
            for position in range(len(sources)):
                content += f"dfs.append(pd.read_csv('{execution.buffer_url(position)}')) \n"

            if execution.incoming_stream is not None:
                content += "payload = '" + json.dumps(execution.incoming_stream) + "' \n"
                content += 'kwargs["stream"] = json.loads(payload) \n'

            content += f"""
print('Starting {transformation.slug}: with '+str(len(dfs))+' dataframes -> '+str(dfs[0].shape))

args_spect = inspect.getfullargspec(run)
if "stream" in kwargs and "stream" not in args_spect.args:
    raise Exception('Transformation needs a "stream" parameter to receive incoming streaming data')

output = run(*dfs[:len(args_spect.args) - len(kwargs.keys())], **kwargs)
print('Ended transformation {transformation.slug}: output -> '+str(output.shape))
output.to_csv('{execution.buffer_url()}', index=False)\n
"""
            logger.debug(f"Executing transformation {transformation.slug}...")
            exec(content, input_vars)
            logger.debug(f"Finalizing transformation {transformation.slug} execution.")
            transformation.status_code = 0
            transformation.status = 'OPERATIONAL'
            transformation.stdout = s.getvalue()

        except Exception as e:
            logger.debug(f"Exception just happened running transformation {transformation.slug}")
            transformation.log_exception(e)
            transformation.status_code = 1
            transformation.status = 'CRITICAL'

    transformation.last_run = timezone.now()
    transformation.save()
    async_backup_buffer.delay(execution.id, position=0)

    logger.debug(
        f"Finished transformation {transformation.slug} execution with status {transformation.status}.")
    return transformation


@shared_task(bind=True, base=BaseTaskWithRetry)
def async_run_transformation(self, execution_id, transformations):
    logger.debug(f'Starting async_run_transformation with {len(transformations)} transformations pending')

    self.log_time_and_memory()
    execution = PipelineExecution.objects.filter(id=execution_id).first()
    if execution is None:
        raise Exception(f'Execution with id {execution_id} not found')
    pipeline = execution.pipeline

    if len(transformations) == 0:
        return True
    
    # avoid concatenation with None down below
    if execution.stdout is None:
        execution.stdout = ""

    if execution.status == 'ABORTED':
        execution.ended_at = timezone.now()
        execution.stdout += 'Aborted by admin user.'
        execution.save()
        return False

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
    execution.save()

    logger.debug(f"{len(transformations)} transformations left to run...")
    if len(transformations) == 0 and t.status == 'OPERATIONAL':
        # no more transformations to apply, save in the database
        logger.debug(f'No more transformations to apply for execution {execution.id}, saving into datasource')
        try:
            logger.debug(f"Saving pipeline {pipeline.slug} buffer to datasource")
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
            logger.debug(f"Error saving buffer for pipeline {pipeline.slug}")
            msg = f'Dataset table not found for {pipeline.source_to.source_type}.{pipeline.source_to.database} -> table: {pipeline.source_to.table_name}'
            pipeline.status = 'CRITICAL'

            execution.stdout += msg
            execution.status = 'CRITICAL'

        except Exception as e:
            logger.exception(f"Error running pipeline {pipeline.slug}")
            pipeline.status = 'CRITICAL'
            execution.log_exception(e)
            execution.status = 'CRITICAL'

    elif len(transformations) > 0 and t.status == 'OPERATIONAL':
        async_run_transformation.delay(execution_id, transformations)

    pipeline.save()
    execution.save()
    self.log_time_and_memory()

    return True


@shared_task(bind=True, base=BaseTaskWithRetry)
def async_run_pipeline(self, pipeline_slug, execution_id=None):

    pipeline = Pipeline.objects.filter(slug=pipeline_slug).first()
    if pipeline is None:
        raise Exception(f'Pipeline {pipeline_slug} not found')

    execution = PipelineExecution.objects.filter(id=execution_id).first()
    if execution is None:
        execution = PipelineExecution(pipeline=pipeline)
        execution.save()  #save to get an id

    execution.started_at = timezone.now()
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
        sources_from = [
            f'{s.source_type}.{s.database} -> table: {s.table_name}' for s in pipeline.source_from.all()
        ]
        execution.stdout += f'Dataset table not found for {" or ".join(sources_from)}'
        execution.status = 'CRITICAL'
    except Exception as e:
        execution.log_exception(e)
        execution.status = 'CRITICAL'

    pipeline.status = execution.status
    execution.save()
    pipeline.save()
    return True

@shared_task(bind=True, base=BaseTaskWithRetry)
def async_backup_buffer(self, execution_id, position=0):
    execution = PipelineExecution.objects.filter(id=execution_id).first()
    if execution is None:
        raise Exception(f'Execution {execution_id} not found')

    execution.backup_buffer(position)

    self.log_time_and_memory()
    return True
