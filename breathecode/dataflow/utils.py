import os
import re
import psycopg2 as pg
import pandas.io.sql as psql
import pandas as pd
from breathecode.services.google_cloud.storage import Storage

from sqlalchemy import create_engine

def is_select_statement(s):
    pattern = re.compile(r"\bSELECT\b", re.IGNORECASE)
    return bool(pattern.search(s))


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
            raise Exception(
                "Missing connection_string while initializing Heroku DB client"
            )
        if "//" not in connection_string:
            connection_string = os.environ.get(connection_string)
        
        # Replace pg.connect with SQLAlchemy create_engine
        # If the connections start with postgres replace with postgresql
        print("connections string: ", connection_string)
        self.connection = create_engine(connection_string.replace("postgres", "postgresql"))
        # self.connection = create_engine(connection_string)

    def get_dataframe_from_table(self, entity_name):
        if len(entity_name) > 7 and is_select_statement(entity_name[0:7]):
            query = entity_name  # it's probably some SQL query instead of an entity name
            print("Executing query: ", query)
            df = psql.read_sql(query, self.connection)
            print("Buffer obtained from Heroku: ", df.shape)
            return df
        else:
            query = f"SELECT * FROM {entity_name}"
            print("Executing query: ", query)
            df = psql.read_sql(query, self.connection)
            print("Buffer obtained from Heroku: ", df.shape)
            return df


class RemoteCSV(object):
    connection = None
    bucket_name = os.environ.get("GOOGLE_BUCKET_NAME", None)
    datastore = None

    def __init__(self, connection_string=None):

        if connection_string is None:
            raise Exception(
                "Please specify file path on google datastore for your CSV source on the connection string input"
            )
        if "gs://" in connection_string:
            self.connection = connection_string
        else:
            self.connection = "gs://" + self.bucket_name + "/" + connection_string

        if self.datastore is None:
            self.datastore = Storage()

    def get_dataframe_from_table(self, entity_name):
        df = pd.read_csv(self.connection)
        return df

    def save_dataframe_to_table(
        self, df, entity_name, replace=False, quoted_newlines=False
    ):

        filename = os.path.basename(entity_name)
        without_extension = os.path.splitext(filename)[0]

        print("Saving to ", self.bucket_name, without_extension + ".csv")
        file = self.datastore.file(self.bucket_name, without_extension + ".csv")
        return file.upload(df.to_csv(index=False), content_type="text/csv")
