import os
import sqlite3
import textwrap

from conan.api.output import ConanOutput
from conans.migrations import Migrator
from conans.util.dates import timestamp_now
from conans.util.files import load, save

CONAN_GENERATED_COMMENT = "This file was generated by Conan"


def update_file(file_path, new_content):
    """
    Update any file path given with the new content.
    Notice that the file is only updated whether it contains the ``CONAN_GENERATED_COMMENT``.

    :param file_path: ``str`` path to the file.
    :param new_content: ``str`` content to be saved.
    """
    out = ConanOutput()
    file_name = os.path.basename(file_path)

    if not os.path.exists(file_path):
        save(file_path, new_content)
    else:
        content = load(file_path)

        first_line = content.lstrip().split("\n", 1)[0]

        if CONAN_GENERATED_COMMENT in first_line and content != new_content:
            save(file_path, new_content)
            out.success(f"Migration: Successfully updated {file_name}")


class ClientMigrator(Migrator):

    def __init__(self, cache_folder, current_version):
        self.cache_folder = cache_folder
        super(ClientMigrator, self).__init__(cache_folder, current_version)

    def _apply_migrations(self, old_version):
        # Migrate the settings if they were the default for that version
        # Time for migrations!
        # Update settings.yml
        from conans.client.conf import migrate_settings_file
        migrate_settings_file(self.cache_folder)
        # Update compatibility.py, app_compat.py, and cppstd_compat.py.
        from conans.client.graph.compatibility import migrate_compatibility_files
        migrate_compatibility_files(self.cache_folder)
        # Update profile plugin
        from conans.client.profile_loader import migrate_profile_plugin
        migrate_profile_plugin(self.cache_folder)

        if old_version and old_version < "2.0.14-":
            _migrate_pkg_db_lru(self.cache_folder, old_version)


def _migrate_pkg_db_lru(cache_folder, old_version):
    ConanOutput().warning(f"Upgrade cache from Conan version '{old_version}'")
    ConanOutput().warning("Running 2.0.14 Cache DB migration to add LRU column")
    db_filename = os.path.join(cache_folder, 'p', 'cache.sqlite3')
    connection = sqlite3.connect(db_filename, isolation_level=None,
                                 timeout=1, check_same_thread=False)
    try:
        lru = timestamp_now()
        for table in ("recipes", "packages"):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN 'lru' "
                               f"INTEGER DEFAULT '{lru}' NOT NULL;")
    except Exception:
        ConanOutput().error(f"Could not complete the 2.0.14 DB migration."
                            " Please manually remove your .conan2 cache and reinstall packages",
                            error_type="context")
        raise
    else:  # generate the back-migration script
        undo_lru = textwrap.dedent("""\
            import os
            import sqlite3
            def migrate(cache_folder):
                db = os.path.join(cache_folder, 'p', 'cache.sqlite3')
                connection = sqlite3.connect(db, isolation_level=None, timeout=1,
                                             check_same_thread=False)
                rec_cols = 'reference, rrev, path, timestamp'
                pkg_cols = 'reference, rrev, pkgid, prev, path, timestamp, build_id'
                try:
                    for table in ("recipes", "packages"):
                        columns = pkg_cols if table == "packages" else rec_cols
                        connection.execute(f"CREATE TABLE {table}_backup AS SELECT {columns} FROM {table};")
                        connection.execute(f"DROP TABLE {table};")
                        connection.execute(f"ALTER TABLE {table}_backup RENAME TO {table};")
                finally:
                    connection.close()
            """)
        path = os.path.join(cache_folder, "migrations", f"2.0.14_1-migrate.py")
        save(path, undo_lru)
    finally:
        connection.close()
