import os
import psycopg2 as pg
import pandas.io.sql as psql


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
