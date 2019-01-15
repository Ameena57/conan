import json
import os
from os.path import join, normpath

from conans.model.editable_cpp_info import EditableCppInfo
from conans.model.ref import ConanFileReference
from conans.util.files import load, save


EDITED_PACKAGES = 'edited_packages'
LAYOUTS_FOLDER = 'layouts'
DEFAULT_LAYOUT_FILE = "default"


class EditedPackages(object):
    def __init__(self, cache_folder):
        self._cache_folder = cache_folder
        self._edited_file = normpath(join(cache_folder, EDITED_PACKAGES))
        if os.path.exists(self._edited_file):
            edited = load(self._edited_file)
            edited_js = json.loads(edited)
            self._edited_refs = {ConanFileReference.loads(r, validate=False): d
                                 for r, d in edited_js.items()}
        else:
            self._edited_refs = {}  # {ref: {"path": path, "layout": layout}}
        self._editable_cpp_info = {}  # Lazy dict

    def save(self):
        d = {str(ref): d for ref, d in self._edited_refs.items()}
        save(self._edited_file, json.dumps(d))

    def get(self, ref):
        ref = ref.copy_clear_rev()
        return self._edited_refs.get(ref)

    def link(self, ref, path, layout):
        assert isinstance(ref, ConanFileReference)
        ref = ref.copy_clear_rev()
        self._edited_refs[ref] = {"path": path, "layout": layout}
        self.save()

    def remove(self, ref):
        assert isinstance(ref, ConanFileReference)
        ref = ref.copy_clear_rev()
        if self._edited_refs.pop(ref, None):
            self.save()
            return True
        return False

    def editable_cpp_info(self, layout_name):
        layout_name = layout_name or DEFAULT_LAYOUT_FILE
        try:
            layout = self._editable_cpp_info[layout_name]
        except KeyError:
            layout_file = os.path.join(self._cache_folder, LAYOUTS_FOLDER, layout_name)
            layout = EditableCppInfo.load(layout_file, True) if os.path.isfile(layout_file) else None
            self._editable_cpp_info[layout_name] = layout
        return layout
