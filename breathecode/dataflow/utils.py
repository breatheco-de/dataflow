import os
import psycopg2 as pg
import pandas.io.sql as psql
import pandas as pd
from breathecode.services.google_cloud.storage import Storage


class PipelineException(Exception):
    pipeline_slug = None
    failed_transformation = None
    stdout = None

    def __init__(self, pipeline, transformation):
        self.pipeline_slug = pipeline.slug
        self.failed_transformation = transformation.slug
        self.stdout = transformation.stdout


class HerokuDB(object):
    connection = None

    def __init__(self, connection_string=None):

        if connection_string is None:
            raise Exception('Missing connection_string while initializing Heroku DB client')
        if '//' not in connection_string:
            connection_string = os.environ.get(connection_string)
        self.connection = pg.connect(dsn=connection_string)

    def get_dataframe_from_table(self, entity_name):
        df = psql.read_sql(f'SELECT * FROM {entity_name}', self.connection)
        return df


class RemoteCSV(object):
    connection = None
    bucket_name = os.environ.get('GOOGLE_BUCKET_NAME', None)

    def __init__(self, connection_string=None):

        if connection_string is None:
            raise Exception(
                'Please specify file path on google datastore for your CSV source on the connection string input'
            )
        if 'gs://' in connection_string:
            self.connection = connection_string
        else:
            self.connection = 'gs://' + self.bucket_name + '/' + connection_string

    def get_dataframe_from_table(self, entity_name):
        df = pd.read_csv(self.connection)
        return df

    def save_dataframe_to_table(self, df, entity_name, replace=False, quoted_newlines=False):

        filename = os.path.basename(entity_name)
        without_extension = os.path.splitext(filename)[0]

        print('Saving to ', self.bucket_name, without_extension + '.csv')
        file = Storage().file(self.bucket_name, without_extension + '.csv')
        return file.upload(df.to_csv(index=False), content_type='text/csv')
