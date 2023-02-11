import sqlite3
from collections import namedtuple
from contextlib import contextmanager
from typing import Tuple, List, Optional


class BaseDbTable:
    table_name: str = None
    columns_description: List[Tuple[str, type]] = None
    row_type: namedtuple = None
    columns: namedtuple = None
    unique_together: tuple = None

    def __init__(self, filename):
        self.filename = filename
        column_names: List[str] = [it[0] for it in self.columns_description]
        self.row_type = namedtuple('_', column_names)
        self.columns = self.row_type(*column_names)
        self.create_table()

    @contextmanager
    def db_connection(self):
        try:
            connection = sqlite3.connect(self.filename, isolation_level=None,
                                        timeout=1, check_same_thread=False)
            yield connection
        finally:
            connection.close()

    def create_table(self):
        def field(name, typename, nullable=False, check_constraints: Optional[List] = None,
                  unique=False):
            field_str = name
            if typename in [str, ]:
                field_str += ' text'
            elif typename in [int, ]:
                field_str += ' integer'
            elif typename in [float, ]:
                field_str += ' real'
            else:
                assert False, f"sqlite3 type not mapped for type '{typename}'"

            if not nullable:
                field_str += ' NOT NULL'

            if check_constraints:
                constraints = ', '.join([str(it) for it in check_constraints])
                field_str += f' CHECK ({name} IN ({constraints}))'

            if unique:
                field_str += ' UNIQUE'

            return field_str

        fields = ', '.join([field(*it) for it in self.columns_description])
        guard = 'IF NOT EXISTS'
        table_checks = f", UNIQUE({', '.join(self.unique_together)})" if self.unique_together else ''
        with self.db_connection() as conn:
            conn.execute(f"CREATE TABLE {guard} {self.table_name} ({fields} {table_checks});")

    def dump(self):
        print(f"********* BEGINTABLE {self.table_name}*************")
        with self.db_connection() as conn:
            r = conn.execute(f'SELECT rowid, * FROM {self.table_name}')
            for it in r.fetchall():
                print(str(it))
            print(f"********* ENDTABLE {self.table_name}*************")
