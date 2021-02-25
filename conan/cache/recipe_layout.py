import os
import uuid
from contextlib import contextmanager, ExitStack
from typing import List

from conan.cache.cache import Cache
from conan.cache.cache_folder import CacheFolder
from conan.cache.package_layout import PackageLayout
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class RecipeLayout(LockableMixin):
    _random_rrev = False

    def __init__(self, ref: ConanFileReference, cache: Cache, **kwargs):
        self._ref = ref
        if not self._ref.revision:
            self._random_rrev = True
            self._ref = ref.copy_with_rev(str(uuid.uuid4()))
        self._cache = cache

        # Get the base_directory that is assigned to this ref.
        default_path = self._cache._backend.get_default_reference_path(ref)
        self._base_directory = \
            self._cache._backend.get_or_create_reference_directory(self._ref, path=default_path)

        # Add place for package layouts
        self._package_layouts: List[PackageLayout] = []
        resource_id = self._ref.full_str()
        super().__init__(resource=resource_id, **kwargs)

    def assign_rrev(self, ref: ConanFileReference, move_contents: bool = False):
        assert str(ref) == str(self._ref), "You cannot change the reference here"
        assert self._random_rrev, "You can only change it if it was not assigned at the beginning"
        assert ref.revision, "It only makes sense to change if you are providing a revision"
        assert not self._package_layouts, "No package_layout is created before the revision is known"
        new_resource: str = ref.full_str()

        # Block the recipe and all the packages too
        with self.exchange(new_resource):
            # Assign the new revision
            old_ref = self._ref
            self._ref = ref
            self._random_rrev = False

            # Reassign folder in the database (only the recipe-folders)
            new_path = self._cache._move_rrev(old_ref, self._ref, move_contents)
            if new_path:
                self._base_directory = new_path

    def get_package_layout(self, pref: PackageReference) -> PackageLayout:
        assert str(pref.ref) == str(self._ref), "Only for the same reference"
        assert not self._random_rrev, "When requesting a package, the rrev is already known"
        assert self._ref.revision == pref.ref.revision, "Ensure revision is the same"
        layout = PackageLayout(self, pref, cache=self._cache, manager=self._manager)
        self._package_layouts.append(layout)  # TODO: Not good, persists even if it is not used
        return layout

    @contextmanager
    def lock(self, blocking: bool, wait: bool = True):  # TODO: Decide if we want to wait by default
        # I need the same level of blocking for all the packages
        with ExitStack() as stack:
            if blocking:
                for package_layout in self._package_layouts:
                    stack.enter_context(package_layout.lock(blocking, wait))
            stack.enter_context(super().lock(blocking, wait))
            yield

    # These folders always return a final location (random) inside the cache.
    @property
    def base_directory(self):
        with self.lock(blocking=False):
            return os.path.join(self._cache.base_folder, self._base_directory)

    def export(self):
        export_directory = lambda: os.path.join(self.base_directory, 'export')
        return CacheFolder(export_directory, False, manager=self._manager, resource=self._resource)

    def export_sources(self):
        export_sources_directory = lambda: os.path.join(self.base_directory, 'export_sources')
        return CacheFolder(export_sources_directory, False, manager=self._manager,
                           resource=self._resource)

    def source(self):
        source_directory = lambda: os.path.join(self.base_directory, 'source')
        return CacheFolder(source_directory, False, manager=self._manager, resource=self._resource)
