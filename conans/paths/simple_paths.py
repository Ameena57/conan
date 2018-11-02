import os

from conans.paths.package_layouts import PackageEditableLayout, PackageCacheLayout
from conans.model.ref import ConanFileReference
from conans.paths import LINKED_FOLDER_SENTINEL, is_case_insensitive_os
from conans.errors import ConanException


if is_case_insensitive_os():
    def check_ref_case(conan_reference, store_folder):
        if not os.path.exists(store_folder):
            return

        tmp = store_folder
        for part in conan_reference:
            items = os.listdir(tmp)
            try:
                idx = [item.lower() for item in items].index(part.lower())
                if part != items[idx]:
                    raise ConanException("Requested '%s' but found case incompatible '%s'\n"
                                         "Case insensitive filesystem can't manage this"
                                         % (str(conan_reference), items[idx]))
                tmp = os.path.normpath(tmp + os.sep + part)
            except ValueError:
                return
else:
    def check_ref_case(conan_reference, store_folder):  # @UnusedVariable
        pass


class SimplePaths(object):
    """
    Generate Conan paths. Handles the conan domain path logic. NO DISK ACCESS, just
    path logic responsability
    """
    def __init__(self, store_folder):
        self._store_folder = store_folder

    @property
    def store(self):
        return self._store_folder

    def package_layout(self, conan_reference, short_paths=False):
        assert isinstance(conan_reference, ConanFileReference)
        base_folder = os.path.normpath(os.path.join(self.store, "/".join(conan_reference)))

        linked_package_file = os.path.join(base_folder, LINKED_FOLDER_SENTINEL)
        if os.path.exists(linked_package_file):
            return PackageEditableLayout(linked_package_file=linked_package_file,
                                         conan_ref=conan_reference)
        else:
            check_ref_case(conan_reference, self.store)
            return PackageCacheLayout(base_folder=base_folder,
                                      conan_ref=conan_reference, short_paths=short_paths)

    def conan(self, conan_reference):
        """ the base folder for this package reference, for each ConanFileReference
        """
        return self.package_layout(conan_reference).conan()

    def export(self, conan_reference):
        return self.package_layout(conan_reference).export()

    def export_sources(self, conan_reference, short_paths=False):
        return self.package_layout(conan_reference, short_paths).export_sources()

    def source(self, conan_reference, short_paths=False):
        return self.package_layout(conan_reference, short_paths).source()

    def conanfile(self, conan_reference):
        return self.package_layout(conan_reference).conanfile()

    def builds(self, conan_reference):
        return self.package_layout(conan_reference).builds()

    def build(self, package_reference, short_paths=False):
        return self.package_layout(package_reference.conan, short_paths).build(package_reference)

    def system_reqs(self, conan_reference):
        return self.package_layout(conan_reference).system_reqs()

    def system_reqs_package(self, package_reference):
        return self.package_layout(package_reference.conan).system_reqs_package(package_reference)

    def packages(self, conan_reference):
        return self.package_layout(conan_reference).packages()

    def package(self, package_reference, short_paths=False):
        return self.package_layout(package_reference.conan, short_paths).package(package_reference)

    def scm_folder(self, conan_reference):
        return self.package_layout(conan_reference).scm_folder()

    def installed_as_editable(self, conan_reference):
        return self.package_layout(conan_reference).installed_as_editable()
