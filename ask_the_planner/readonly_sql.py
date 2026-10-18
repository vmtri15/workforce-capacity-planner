"""A read only SQL runner for Vanna.

Vanna's built in SqliteRunner opens the database read write and commits any INSERT, UPDATE or DELETE it
is given. This runner cannot change the database, in three layers:
  1. only a single SELECT statement (including WITH ... SELECT) is accepted
  2. the file is opened with SQLite's read only mode (mode=ro)
  3. PRAGMA query_only is switched on for the connection
Every statement and result is kept in `log`, so an evaluation can see exactly what the model ran.
"""
import sqlite3
from pathlib import Path

import pandas as pd
import sqlparse
from vanna.capabilities.sql_runner import RunSqlToolArgs, SqlRunner
from vanna.core.tool import ToolContext

MAX_ROWS = 500


class ReadOnlyViolation(ValueError):
    """Raised when a statement is not a single SELECT."""


def check_select_only(sql: str) -> str:
    statements = [s for s in sqlparse.split(sql) if s.strip().strip(';').strip()]
    if len(statements) != 1:
        raise ReadOnlyViolation('Exactly one SQL statement is allowed.')
    statement = statements[0].strip().rstrip(';').strip()
    if sqlparse.parse(statement)[0].get_type() != 'SELECT':
        raise ReadOnlyViolation('Only SELECT queries are allowed. This database is read only.')
    return statement


def connect_read_only(database_path) -> sqlite3.Connection:
    uri = Path(database_path).resolve().as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    connection.execute('PRAGMA query_only = ON')
    return connection


class ReadOnlySqlRunner(SqlRunner):
    def __init__(self, database_path):
        self.database_path = Path(database_path).resolve()
        self.log = []

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame:
        entry = dict(sql=args.sql, error=None, result=None)
        self.log.append(entry)
        try:
            statement = check_select_only(args.sql)
            connection = connect_read_only(self.database_path)
            try:
                frame = pd.read_sql_query(statement, connection)
            finally:
                connection.close()
        except Exception as error:
            entry['error'] = f'{type(error).__name__}: {error}'
            raise
        entry['result'] = frame
        return frame.head(MAX_ROWS)
