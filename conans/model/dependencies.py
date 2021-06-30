from collections import OrderedDict

from conans.client.graph.graph import BINARY_SKIP
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement


class UserRequirementsDict(object):
    """ user facing dict to allow access of dependencies by name
    """
    def __init__(self, data, require_filter=None):
        self._data = data  # dict-like
        self._require_filter = require_filter  # dict {trait: value} for requirements

    def filter(self, require_filter):
        def filter_fn(require):
            for k, v in require_filter.items():
                if getattr(require, k) != v:
                    return False
            return True
        data = OrderedDict((k, v) for k, v in self._data.items() if filter_fn(k))
        return UserRequirementsDict(data, require_filter)

    def __bool__(self):
        return bool(self._data)

    __nonzero__ = __bool__

    def _get_require(self, ref, **kwargs):
        assert isinstance(ref, str)
        if "/" in ref:
            ref = ConanFileReference.loads(ref)
        else:
            ref = ConanFileReference(ref, "unknown", "unknown", "unknown", validate=False)

        if self._require_filter:
            kwargs.update(self._require_filter)
        r = Requirement(ref, **kwargs)
        return r

    def get(self, ref, **kwargs):
        r = self._get_require(ref, **kwargs)
        return self._data.get(r)

    def __getitem__(self, name):
        r = self._get_require(name)
        return self._data[r]

    def __delitem__(self, name):
        r = self._get_require(name)
        del self._data[r]

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


class ConanFileDependencies(UserRequirementsDict):

    @staticmethod
    def from_node(node):
        d = OrderedDict((require, ConanFileInterface(transitive.node.conanfile))
                        for require, transitive in node.transitive_deps.items()
                        if transitive.node.binary != BINARY_SKIP)
        return ConanFileDependencies(d)

    def filter(self, require_filter):
        return super(ConanFileDependencies, self).filter(require_filter)

    @property
    def direct_host(self):
        return self.filter({"build": False, "direct": True})

    @property
    def direct_build(self):
        return self.filter({"build": True, "direct": True, "run": True})

    @property
    def host(self):
        return self.filter({"build": False})

    @property
    def build(self):
        return self.filter({"build": True, "run": True})
