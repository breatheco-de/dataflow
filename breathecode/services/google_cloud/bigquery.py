import json
import logging
import os
import traceback
import re
from datetime import datetime
from .credentials import resolve_credentials
from .storage import Storage
from google.api_core import retry
from google.cloud import bigquery
import pytz

logger = logging.getLogger(__name__)


def now():
    return datetime.utcnow().replace(tzinfo=pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')

def is_select_statement(s):
    pattern = re.compile(r'\bSELECT\b', re.IGNORECASE)
    return bool(pattern.search(s))

class BigQueryError(Exception):
    '''Exception raised whenever a BigQuery error happened'''

    def __init__(self, errors):
        super().__init__(self._format(errors))
        self.errors = errors

    def _format(self, errors):
        err = []
        for error in errors:
            err.extend(error['errors'])
        return json.dumps(err)


class BigQuery:
    """Google Cloud Storage"""
    client = None
    dataset = None
    bucket_name = os.environ.get('GOOGLE_BUCKET_NAME', None)

    def __init__(self, dataset=None):

        if dataset is None:
            raise BigQueryError('Missing dataset while initializing BigQuery client')
        if self.bucket_name is None:
            raise Exception('Missing bucket nam for dataflow csv files')

        resolve_credentials()
        self.client = bigquery.Client()
        self.dataset = dataset

    def stream_into(self, entity_name, data):
        '''This function is executed whenever a file is added to Cloud Storage'''
        try:
            self.insert_into(entity_name, data)
            self.success(entity_name)
        except Exception:
            self.error(entity_name)

    def insert_into(self, entity_name, data):
        table = self.client.dataset(self.dataset).table(entity_name)
        errors = self.client.insert_rows_json(table, [data], retry=retry.Retry(deadline=30))
        if errors != []:
            raise BigQueryError(errors)

    def get_dataframe_from_table(self, entity_name):

        if len(entity_name) > 7 and is_select_statement(entity_name[0:7]):
            # Append a limit clause to the SQL query
            entity_name = f"{entity_name} LIMIT 50000"
            query_job = self.client.query(entity_name)  # SQL Query
            df = query_job.to_dataframe()
        else:
            table = self.client.dataset(self.dataset).table(entity_name)
            # Get the last 50000 rows
            total_rows = self.client.get_table(table).num_rows
            rows_to_skip = max(0, total_rows - 50000)
            df = self.client.list_rows(table, start_index=rows_to_skip).to_dataframe()
            
        return df

    def save_dataframe_to_table(self, df, entity_name, replace=False, quoted_newlines=True):

        file = Storage().file(self.bucket_name, f'{entity_name}.csv')
        file.upload(df.to_csv(index=False), content_type='text/csv')

        table = self.client.dataset(self.dataset).table(entity_name)

        if replace:
            self.client.delete_table(table, not_found_ok=True)

        # Define storage bucket
        job_config = bigquery.LoadJobConfig(
            autodetect=True,
            skip_leading_rows=1,
            create_disposition='CREATE_IF_NEEDED',
            allow_quoted_newlines=quoted_newlines,
            # The source format defaults to CSV, so the line below is optional.
            source_format=bigquery.SourceFormat.CSV,
        )

        load_job = self.client.load_table_from_uri(f'gs://{self.bucket_name}/{entity_name}.csv',
                                                   table,
                                                   job_config=job_config)  # Make an API request.

        load_job.result()

        # table.num_rows will give you the number of rows in the table. More than 0 is good
        return table

    def success(self, event_name):
        logger.info(f'Event {event_name} streamed into BigQuery')
        logger.success({
            u'success': True,
            u'created_at': now(),
            u'event_name': event_name,
        })

    def error(self, event_name):
        message = 'Error streaming event \'%s\'. Cause: %s' % (event_name, traceback.format_exc())
        logger.error({
            u'success': False,
            u'error_message': message,
            u'created_at': now(),
            u'event_name': event_name,
        })
