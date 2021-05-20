import sqlite3
import time
from collections import namedtuple
from io import StringIO
from typing import List, Iterator

from conan.cache.db.table import BaseDbTable
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference


class ReferencesDbTable(BaseDbTable):
    table_name = 'conan_references'
    columns_description = [('reference', str),
                           ('rrev', str),
                           ('pkgid', str, True),
                           ('prev', str, True),
                           ('path', str, False, None, True),
                           ('timestamp', int),
                           ('remote', str, True)]
    unique_together = ('reference', 'rrev', 'pkgid', 'prev')

    class DoesNotExist(ConanException):
        pass

    class MultipleObjectsReturned(ConanException):
        pass

    class AlreadyExist(ConanException):
        pass

    def _as_dict(self, row: namedtuple):
        return {
            "reference": row.reference,
            "rrev": row.rrev,
            "pkgid": row.pkgid,
            "prev": row.prev,
            "path": row.path,
            "timestamp": row.timestamp,
            "remote": row.remote
        }

    def _as_ref(self, row: namedtuple):
        if row.prev:
            return PackageReference.loads(f'{row.reference}#{row.rrev}:{row.pkgid}#{row.prev}',
                                          validate=False)
        else:
            return ConanFileReference.loads(f'{row.reference}#{row.rrev}', validate=False)

    def _where_clause(self, ref):
        where_dict = {
            self.columns.reference: ref.reference,
            self.columns.rrev: ref.rrev,
            self.columns.pkgid: ref.pkgid,
            self.columns.prev: ref.prev,
        }
        where_expr = ' AND '.join(
            [f'{k}="{v}" ' if v is not None else f'{k} IS NULL' for k, v in where_dict.items()])
        return where_expr

    def _set_clause(self, ref, path=None, timestamp=None, remote=None):
        set_dict = {
            self.columns.reference: ref.reference,
            self.columns.rrev: ref.rrev,
            self.columns.pkgid: ref.pkgid,
            self.columns.prev: ref.prev,
            self.columns.path: path,
            self.columns.timestamp: timestamp,
            self.columns.remote: remote,
        }
        set_expr = ', '.join([f'{k} = "{v}"' for k, v in set_dict.items() if v is not None])
        return set_expr

    def get_path_ref(self, conn: sqlite3.Cursor, ref) -> str:
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(ref)
        query = f'SELECT {self.columns.path} FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ReferencesDbTable.DoesNotExist(
                f"No entry for reference '{ref.full_reference}'")
        return row[0]

    def get_remote(self, conn: sqlite3.Cursor, ref):
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(ref)
        query = f'SELECT {self.columns.remote} FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ReferencesDbTable.DoesNotExist(
                f"No entry for reference '{ref.full_reference}'")
        return row[0]

    def save(self, conn: sqlite3.Cursor, path, ref, remote=None) -> int:
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})',
                         [ref.reference, ref.rrev, ref.pkgid, ref.prev, path, timestamp, remote])
        return r.lastrowid

    def update(self, conn: sqlite3.Cursor, old_ref, new_ref=None, new_path=None, new_remote=None):
        if not new_ref:
            new_ref = old_ref
        timestamp = int(time.time())
        where_clause = self._where_clause(old_ref)
        set_clause = self._set_clause(new_ref, path=new_path, timestamp=timestamp, remote=new_remote)
        query = f"UPDATE {self.table_name} " \
                f"SET {set_clause} " \
                f"WHERE {where_clause};"
        r = conn.execute(query)
        return r.lastrowid

    def delete_by_path(self, conn: sqlite3.Cursor, path):
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE path = ?;"
        r = conn.execute(query, (path,))
        return r.lastrowid

    def remove(self, conn: sqlite3.Cursor, ref):
        where_clause = self._where_clause(ref)
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE {where_clause};"
        r = conn.execute(query)
        return r.lastrowid

    def get(self, conn: sqlite3.Cursor, pk: int) -> ConanFileReference:
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE rowid = ?;'
        r = conn.execute(query, [pk, ])
        row = r.fetchone()
        return self._as_ref(self.row_type(*row))

    def all(self, conn: sqlite3.Cursor, only_latest_rrev: bool) -> List[ConanFileReference]:
        if only_latest_rrev:
            query = f'SELECT DISTINCT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'{self.columns.remote}, ' \
                    f'MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.prev} IS NULL ' \
                    f'GROUP BY {self.columns.reference} ' \
                    f'ORDER BY MAX({self.columns.timestamp}) ASC'
        else:
            query = f'SELECT * FROM {self.table_name} WHERE {self.columns.prev} IS NULL;'
        r = conn.execute(query)
        for row in r.fetchall():
            yield self._as_ref(self.row_type(*row))

    def latest_rrev(self, conn: sqlite3.Cursor, ref: ConanFileReference) -> ConanFileReference:
        """ Returns the latest ref according to rrev """
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {self.columns.reference} = ? ' \
                f'ORDER BY {self.columns.rrev} ' \
                f'LIMIT 1;'
        r = conn.execute(query, [str(ref), ])
        row = r.fetchone()
        return self._as_ref(self.row_type(*row))

    def get_prevs(self, conn: sqlite3.Cursor, ref, only_latest_prev: bool = False) -> List[
        PackageReference]:
        assert ref.rrev, "To search for package revisions you must provide a recipe revision."
        check_pkgid = f'AND {self.columns.pkgid} = "{ref.pkgid}" ' if ref.pkgid else ''
        if only_latest_prev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'{self.columns.remote}, ' \
                    f'MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                    f'AND {self.columns.reference} = "{ref.reference}" ' \
                    f'{check_pkgid} ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'GROUP BY {self.columns.pkgid} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                    f'AND {self.columns.reference} = "{ref.reference}" ' \
                    f'{check_pkgid} ' \
                    f'AND {self.columns.prev} IS NOT NULL '
        r = conn.execute(query)
        for row in r.fetchall():
            yield self._as_ref(self.row_type(*row))

    def get_rrevs(self, conn: sqlite3.Cursor, ref, only_latest_rrev: bool = False):
        check_rrev = f'AND {self.columns.rrev} = "{ref.rrev}" ' if ref.rrev else ''
        if only_latest_rrev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'{self.columns.remote}, ' \
                    f'MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} = "{ref.reference}" ' \
                    f'AND {self.columns.prev} IS NULL ' \
                    f'AND {self.columns.pkgid} IS NULL ' \
                    f'{check_rrev} ' \
                    f'GROUP BY {self.columns.pkgid} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} = "{ref.reference}" ' \
                    f'AND {self.columns.prev} IS NULL ' \
                    f'{check_rrev} ' \
                    f'AND {self.columns.pkgid} IS NULL '

        r = conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))

    def get_pkgids(self, conn: sqlite3.Cursor, ref, only_latest_prev=False) -> List[
        PackageReference]:
        assert ref.rrev, "To search for package id's you must provide a recipe revision."
        if only_latest_prev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'{self.columns.remote}, ' \
                    f'MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                    f'AND {self.columns.reference} = "{ref.reference}" ' \
                    f'AND {self.columns.pkgid} IS NOT NULL ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'GROUP BY {self.columns.pkgid} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                    f'AND {self.columns.reference} = "{ref.reference}" ' \
                    f'AND {self.columns.pkgid} IS NOT NULL ' \
                    f'AND {self.columns.prev} IS NOT NULL'
        r = conn.execute(query)
        for row in r.fetchall():
            yield self._as_ref(self.row_type(*row))
