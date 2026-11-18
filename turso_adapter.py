
"""SQLite-style adapter for Turso using HTTPS.

Uses Python's standard library instead of the native
libsql driver.

Each TursoConnection should be used by one request at a time.
"""

import base64
import json
import math
import sqlite3

from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _encode(value):
    """Convert Python values into Turso SQL parameters."""

    if value is None:
        return {"type": "null"}

    if isinstance(value, bool):
        return {
            "type": "integer",
            "value": str(int(value))
        }

    if isinstance(value, int):
        return {
            "type": "integer",
            "value": str(value)
        }

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Invalid SQL float")

        return {
            "type": "float",
            "value": value
        }

    if isinstance(value, str):
        return {
            "type": "text",
            "value": value
        }

    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "type": "blob",
            "base64": base64.b64encode(
                bytes(value)
            ).decode("ascii")
        }

    raise TypeError(
        f"Unsupported SQL parameter: {type(value).__name__}"
    )


def _decode(value):
    """Convert Turso SQL values into Python values."""

    kind = value["type"]

    if kind == "null":
        return None

    if kind == "integer":
        return int(value["value"])

    if kind == "float":
        return float(value["value"])

    if kind == "text":
        return value["value"]

    if kind == "blob":
        return base64.b64decode(value["base64"])

    raise ValueError(f"Unknown SQL value type: {kind}")


def _statement(sql, parameters=()):
    """Build a parameterized SQL statement."""

    stmt = {"sql": sql}

    if isinstance(parameters, dict):
        stmt["named_args"] = [
            {
                "name": name,
                "value": _encode(value)
            }
            for name, value in parameters.items()
        ]

    elif parameters:
        stmt["args"] = [
            _encode(value)
            for value in parameters
        ]

    return {
        "type": "execute",
        "stmt": stmt
    }


class TursoRow(dict):
    """Access a database row by name or index."""

    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]

        return super().__getitem__(key)


class TursoCursor:
    """SQLite-like cursor for Turso HTTP results."""

    def __init__(self, result):
        columns = [
            col.get("name") or f"column_{i}"
            for i, col in enumerate(result.get("cols", []))
        ]

        self._rows = [
            TursoRow(
                columns,
                [_decode(cell) for cell in row]
            )
            for row in result.get("rows", [])
        ]

        self._pos = 0

        last_id = result.get("last_insert_rowid")

        self.lastrowid = (
            int(last_id)
            if last_id is not None
            else None
        )

        self.rowcount = result.get(
            "affected_row_count", -1
        )

        self.description = [
            (name, None, None, None, None, None, None)
            for name in columns
        ]

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None

        row = self._rows[self._pos]
        self._pos += 1

        return row

    def fetchall(self):
        remaining = self._rows[self._pos:]
        self._pos = len(self._rows)

        return remaining


class TursoConnection:
    """Connect to Turso using its HTTP pipeline API."""

    def __init__(
        self,
        database_url,
        auth_token,
        timeout=12
    ):
        url = urlsplit(database_url.strip())

        if (
            url.scheme != "libsql"
            or not url.netloc
            or url.path not in ("", "/")
        ):
            raise ValueError(
                "Expected a Turso libsql://host URL"
            )

        if not auth_token:
            raise ValueError(
                "Turso authentication token is missing"
            )

        self._base_url = f"https://{url.netloc}"
        self._token = auth_token
        self._timeout = timeout

        self._baton = None
        self._transaction = False
        self._closed = False

    def _pipeline(self, requests):
        """Send SQL requests to Turso over HTTPS."""

        if self._closed:
            raise sqlite3.ProgrammingError(
                "Turso connection is closed"
            )

        payload = json.dumps({
            "baton": self._baton,
            "requests": requests
        }).encode("utf-8")

        request = Request(
            f"{self._base_url.rstrip('/')}/v3/pipeline",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout
            ) as response:
                body = json.load(response)

        except HTTPError as error:
            self._closed = True
            raise ConnectionError(
                f"Turso HTTP error {error.code}"
            ) from error

        except (URLError, TimeoutError, OSError) as error:
            self._closed = True
            raise ConnectionError(
                "Turso HTTP connection failed or timed out"
            ) from error

        self._baton = body.get("baton")

        if body.get("base_url"):
            self._base_url = body["base_url"]

        results = body.get("results", [])

        if len(results) != len(requests):
            raise RuntimeError(
                "Turso returned an incomplete response"
            )

        for result in results:
            if result.get("type") == "error":
                error = result.get("error", {})

                message = error.get(
                    "message",
                    "SQL statement failed"
                )

                code = error.get("code", "") or ""

                if (
                    "CONSTRAINT" in code.upper()
                    or "constraint failed" in message.lower()
                ):
                    raise sqlite3.IntegrityError(message)

                raise sqlite3.OperationalError(message)

            if result.get("type") != "ok":
                raise RuntimeError(
                    "Unexpected Turso HTTP result"
                )

        return results

    def execute(self, sql, parameters=()):
        """Execute SQL with optional parameters."""

        statement = _statement(sql, parameters)

        keyword = (
            sql.lstrip().split(None, 1)[0].upper()
            if sql.strip()
            else ""
        )

        if keyword == "BEGIN":
            if self._transaction:
                raise sqlite3.OperationalError(
                    "Transaction already open"
                )

            self._pipeline([
                _statement("BEGIN")
            ])

            self._transaction = True
            return TursoCursor({})

        if keyword == "COMMIT":
            self.commit()
            return TursoCursor({})

        if keyword == "ROLLBACK":
            self.rollback()
            return TursoCursor({})

        begin_transaction = (
            not self._transaction
            and keyword in {
                "INSERT",
                "UPDATE",
                "DELETE",
                "REPLACE"
            }
        )

        if begin_transaction:
            requests = [
                _statement("BEGIN"),
                statement
            ]
        else:
            requests = [statement]

        if not self._transaction and not begin_transaction:
            requests.append({"type": "close"})

        try:
            results = self._pipeline(requests)

        except Exception:
            if (
                begin_transaction
                and self._baton
                and not self._closed
            ):
                self._transaction = True

                try:
                    self.rollback()
                except Exception:
                    pass

            raise

        if begin_transaction:
            self._transaction = True

        if self._transaction and not self._baton:
            raise ConnectionError(
                "Turso closed a transaction unexpectedly"
            )

        actual = (
            results[1]
            if begin_transaction
            else results[0]
        )

        return TursoCursor(
            actual["response"]["result"]
        )

    def commit(self):
        """Save an active transaction."""

        if self._closed:
            raise sqlite3.ProgrammingError(
                "Turso connection is closed"
            )

        if self._transaction:
            self._pipeline([
                _statement("COMMIT"),
                {"type": "close"}
            ])

            self._transaction = False
            self._baton = None

    def rollback(self):
        """Cancel an active transaction."""

        if self._closed:
            raise sqlite3.ProgrammingError(
                "Turso connection is closed"
            )

        if self._transaction:
            self._pipeline([
                _statement("ROLLBACK"),
                {"type": "close"}
            ])

            self._transaction = False
            self._baton = None

    def close(self):
        """Close the database connection."""

        if not self._closed:
            try:
                if self._transaction:
                    self.rollback()

                elif self._baton:
                    self._pipeline([
                        {"type": "close"}
                    ])

            finally:
                self._closed = True
                self._baton = None

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

        return False
