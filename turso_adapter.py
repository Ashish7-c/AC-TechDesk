
class TursoRow(dict):
    """Allow database rows to be accessed by column name or index."""

    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class TursoCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = [
            col if isinstance(col, str) else col[0]
            for col in (cursor.description or [])
        ]

    def _convert(self, row):
        if row is None:
            return None
        return TursoRow(self._columns, row)

    def fetchone(self):
        return self._convert(self._cursor.fetchone())

    def fetchall(self):
        return [
            self._convert(row)
            for row in self._cursor.fetchall()
        ]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class TursoConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, parameters=()):
        cursor = self._connection.execute(sql, parameters)
        return TursoCursor(cursor)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._connection.__exit__(
            exc_type, exc_value, traceback
        )
