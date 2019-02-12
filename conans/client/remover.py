import os

from conans.client.cache.remote_registry import Remote
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.errors import NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import SYSTEM_REQS, rm_conandir
from conans.search.search import filter_outdated, search_packages, search_recipes
from conans.util.log import logger


class DiskRemover(object):
    def __init__(self, cache):
        self._cache = cache

    def _remove(self, path, ref, msg=""):
        try:
            logger.debug("REMOVE: folder %s" % path)
            rm_conandir(path)
        except OSError:
            error_msg = "Folder busy (open or some file open): %s" % path
            raise ConanException("%s: Unable to remove %s\n\t%s" % (repr(ref), msg, error_msg))

    def _remove_file(self, path, ref, msg=""):
        try:
            logger.debug("REMOVE: file %s" % path)
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            error_msg = "File busy (open): %s" % path
            raise ConanException("Unable to remove %s %s\n\t%s" % (repr(ref), msg, error_msg))

    def remove_recipe(self, ref):
        self.remove_src(ref)
        self._remove(self._cache.export(ref), ref, "export folder")
        self._remove(self._cache.export_sources(ref), ref, "export_source folder")
        for f in self._cache.conanfile_lock_files(ref):
            try:
                os.remove(f)
            except OSError:
                pass

    def remove(self, ref):
        self.remove_recipe(ref)
        self.remove_builds(ref)
        self.remove_packages(ref)
        self._remove(self._cache.conan(ref), ref)

    def remove_src(self, ref):
        self._remove(self._cache.source(ref), ref, "src folder")

    def remove_builds(self, ref, ids=None):
        if not ids:
            path = self._cache.builds(ref)
            for build in self._cache.conan_builds(ref):
                self._remove(os.path.join(path, build), ref, "build folder:%s" % build)
            self._remove(path, ref, "builds")
        else:
            for id_ in ids:
                # Removal build IDs should be those of the build_id if present
                pkg_path = self._cache.build(PackageReference(ref, id_))
                self._remove(pkg_path, ref, "package:%s" % id_)

    def remove_packages(self, ref, ids_filter=None):
        if not ids_filter:  # Remove all
            path = self._cache.packages(ref)
            # Necessary for short_paths removal
            for package in self._cache.conan_packages(ref):
                self._remove(os.path.join(path, package), ref, "package folder:%s" % package)
            self._remove(path, ref, "packages")
            self._remove_file(self._cache.system_reqs(ref), ref, SYSTEM_REQS)
        else:
            for id_ in ids_filter:  # remove just the specified packages
                pref = PackageReference(ref, id_)
                if not self._cache.package_layout(ref).package_exists(pref):
                    raise PackageNotFoundException(pref)
                pkg_folder = self._cache.package(pref)
                self._remove(pkg_folder, ref, "package:%s" % id_)
                self._remove_file(pkg_folder + ".dirty", ref, "dirty flag")
                self._remove_file(self._cache.system_reqs_package(pref), ref,
                                  "%s/%s" % (id_, SYSTEM_REQS))


class ConanRemover(object):
    """ Class responsible for removing locally/remotely conans, package folders, etc. """

    def __init__(self, cache, remote_manager, user_io):
        self._user_io = user_io
        self._cache = cache
        self._remote_manager = remote_manager
        self._registry = cache.registry

    def _remote_remove(self, ref, package_ids, remote):
        assert(isinstance(remote, Remote))
        if package_ids is None:
            result = self._remote_manager.remove(ref, remote)
            return result
        else:
            tmp = self._remote_manager.remove_packages(ref, package_ids, remote)
            return tmp

    @staticmethod
    def _message_removing_editable(ref):
        return "Package '{r}' is installed as editable, unlink it first using " \
               "command 'conan link {r} --remove'".format(r=ref)

    def _local_remove(self, ref, src, build_ids, package_ids):
        if self._cache.installed_as_editable(ref):
            self._user_io.out.warn(self._message_removing_editable(ref))
            return

        # Make sure to clean the locks too
        self._cache.remove_package_locks(ref)
        remover = DiskRemover(self._cache)
        if src:
            remover.remove_src(ref)
        if build_ids is not None:
            remover.remove_builds(ref, build_ids)

        if package_ids is not None:
            remover.remove_packages(ref, package_ids)
            with self._cache.package_layout(ref).update_metadata() as metadata:
                for package_id in package_ids:
                    pref = PackageReference(ref, package_id)
                    self._registry.prefs.remove(pref)
                    metadata.clear_package(package_id)
        if not src and build_ids is None and package_ids is None:
            remover.remove(ref)
            self._registry.refs.remove(ref, quiet=True)
            self._registry.prefs.remove_all(ref)

    def remove(self, pattern, remote_name, src=None, build_ids=None, package_ids_filter=None,
               force=False, packages_query=None, outdated=False):
        """ Remove local/remote conans, package folders, etc.
        @param src: Remove src folder
        @param pattern: it could be OpenCV* or OpenCV or a ConanFileReference
        @param build_ids: Lists with ids or empty for all. (Its a filter)
        @param package_ids_filter: Lists with ids or empty for all. (Its a filter)
        @param force: if True, it will be deleted without requesting anything
        @param packages_query: Only if src is a reference. Query settings and options
        """

        if remote_name and (build_ids is not None or src):
            raise ConanException("Remotes don't have 'build' or 'src' folder, just packages")

        try:
            input_ref = ConanFileReference.loads(pattern)
        except (ConanException, TypeError):
            input_ref = None

        if not input_ref and packages_query is not None:
            raise ConanException("query parameter only allowed with a valid recipe "
                                 "reference as the search pattern.")

        if input_ref and package_ids_filter and not input_ref.revision:
            for package_id in package_ids_filter:
                if "#" in package_id:
                    raise ConanException("Specify a recipe revision if you specify a package "
                                         "revision")

        if remote_name:
            remote = self._registry.remotes.get(remote_name)
            if input_ref:
                if not self._cache.config.revisions_enabled and input_ref.revision:
                    raise ConanException("Revisions not enabled in the client, cannot remove "
                                         "revisions in the server")
                refs = [input_ref]
            else:
                refs = self._remote_manager.search_recipes(remote, pattern)
        else:
            if input_ref:
                refs = []
                if self._cache.installed_as_editable(input_ref):
                    raise ConanException(self._message_removing_editable(input_ref))
                if not self._cache.package_layout(input_ref).recipe_exists():
                    raise RecipeNotFoundException(input_ref,
                                                  print_rev=self._cache.config.revisions_enabled)
                refs.append(input_ref)
            else:
                refs = search_recipes(self._cache, pattern)
                if not refs:
                    self._user_io.out.warn("No package recipe matches '%s'" % str(pattern))
                    return

        if input_ref and not input_ref.revision:
            # Ignore revisions for deleting if the input was not with a revision
            # (Removing all the recipe revisions from a reference)
            refs = [r.copy_clear_rev() for r in refs]

        deleted_refs = []
        for ref in refs:
            assert isinstance(ref, ConanFileReference)
            package_ids = package_ids_filter
            if packages_query or outdated:
                # search packages
                if remote_name:
                    packages = self._remote_manager.search_packages(remote, ref, packages_query)
                else:
                    packages = search_packages(self._cache, ref, packages_query)
                if outdated:
                    if remote_name:
                        recipe_hash = self._remote_manager.get_conan_manifest(ref, remote).summary_hash
                    else:
                        recipe_hash = self._cache.package_layout(ref).load_manifest().summary_hash

                    packages = filter_outdated(packages, recipe_hash)
                if package_ids_filter:
                    package_ids = [p for p in packages if p in package_ids_filter]
                else:
                    package_ids = list(packages.keys())
                if not package_ids:
                    self._user_io.out.warn("No matching packages to remove for %s"
                                           % ref.full_repr())
                    continue

            if self._ask_permission(ref, src, build_ids, package_ids, force):
                try:
                    if remote_name:
                        self._remote_remove(ref, package_ids, remote)
                    else:
                        self._local_remove(ref, src, build_ids, package_ids)
                except NotFoundException:
                    # If we didn't specify a pattern but a concrete ref, fail if there is no
                    # ref to remove
                    if input_ref:
                        raise
                else:
                    deleted_refs.append(ref)

        if not remote_name:
            self._cache.delete_empty_dirs(deleted_refs)

    def _ask_permission(self, ref, src, build_ids, package_ids_filter, force):
        def stringlist(alist):
            return ", ".join(['"%s"' % p for p in alist])

        if force:
            return True
        aux_str = []
        if src:
            aux_str.append(" src folder")
        if build_ids is not None:
            if build_ids:
                aux_str.append(" %s builds" % stringlist(build_ids))
            else:
                aux_str.append(" all builds")
        if package_ids_filter is not None:
            if package_ids_filter:
                aux_str.append(" %s packages" % stringlist(package_ids_filter))
            else:  # All packages to remove, no filter
                aux_str.append(" all packages")
        return self._user_io.request_boolean("Are you sure you want to delete%s from '%s'"
                                             % (", ".join(aux_str), str(ref)))
