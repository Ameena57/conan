import os
from io import StringIO

from conan.locks.backend import LockBackend
from conan.locks.exceptions import AlreadyLockedException
from conan.utils.sqlite3 import Sqlite3MemoryMixin, Sqlite3FilesystemMixin


class LockBackendSqlite3(LockBackend):
    # Sqlite3 backend to store locks. It will store the PID of every writer or reader before
    # the can proceed to the resource (exclusive writer strategy).

    LockId = int
    _table_name = 'conan_locks'
    _column_resource = 'resource'
    _column_pid = 'pid'
    _column_writer = 'writer'

    def dump(self, output: StringIO):
        with self.connect() as conn:
            r = conn.execute(f'SELECT * FROM {self._table_name}')
            for it in r.fetchall():
                output.write(it)

    def create_table(self, if_not_exists: bool = True):
        guard = 'IF NOT EXISTS' if if_not_exists else ''
        query = f"""
        CREATE TABLE {guard} {self._table_name} (
            {self._column_resource} text NOT NULL,
            {self._column_pid} integer NOT NULL,
            {self._column_writer} BOOLEAN NOT NULL CHECK ({self._column_writer} IN (0,1))
        );
        """
        with self.connect() as conn:
            conn.execute(query)

    def try_acquire(self, resource: str, blocking: bool) -> LockId:
        # Returns a backend-id
        # TODO: Detect dead-lock based on pid
        with self.connect() as conn:
            # Check if any is using the resource
            result = conn.execute(f'SELECT {self._column_pid}, {self._column_writer} '
                                  f'FROM {self._table_name} '
                                  f'WHERE {self._column_resource} = "{resource}";')
            if blocking and result.fetchone():
                raise AlreadyLockedException(resource)

            # Check if a writer (exclusive) is blocking
            blocked = any([it[1] for it in result.fetchall()])
            if blocked:
                raise AlreadyLockedException(resource, by_writer=True)

            # Add me as a blocker, reader or writer
            blocking_value = 1 if blocking else 0
            result = conn.execute(f'INSERT INTO {self._table_name} '
                                  f'VALUES ("{resource}", {os.getpid()}, {blocking_value})')
            return result.lastrowid

    def release(self, backend_id: LockId):
        with self.connect() as conn:
            conn.execute(f'DELETE FROM {self._table_name} WHERE rowid={backend_id}')


class LockBackendSqlite3Memory(Sqlite3MemoryMixin, LockBackendSqlite3):
    pass


class LockBackendSqlite3Filesystem(Sqlite3FilesystemMixin, LockBackendSqlite3):
    pass
