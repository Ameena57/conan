from conans.model.ref import ConanFileReference
from conans.errors import ConanException
from conans.model.version import Version
import re


class RequireResolver(object):
    expr_pattern = re.compile("")

    def __init__(self, output, local_search, remote_search):
        self._output = output
        self._local_search = local_search
        self._remote_search = remote_search

    def resolve(self, require):
        version_range = require.version_range()
        if version_range is None:
            return

        ref = require.conan_reference
        search_ref = ConanFileReference(ref.name, "*", ref.user, ref.channel)
        resolved = self._resolve_local(search_ref, version_range)
        if not resolved:
            remote_found = self._remote_search.search_remotes(search_ref)
            if remote_found:
                resolved = self._resolve_version(version_range, remote_found)

        if resolved:
            require.conan_reference = resolved
        else:
            raise ConanException("The version in '%s' could not be resolved" % version_range)

    def _resolve_local(self, search_ref, version_range):
        if self._local_search:
            local_found = self._local_search.search(search_ref)
            if local_found:
                resolved_version = self._resolve_version(version_range, local_found)
                if resolved_version:
                    return resolved_version

    def _resolve_version(self, version_range, local_found):
        version_range = version_range.replace(",", " ")
        versions = {Version(ref.version): ref for ref in local_found}
        sorted_versions = reversed(sorted(versions))
        from semver import max_satisfying
        result = max_satisfying(sorted_versions, version_range, loose=True)
        return versions.get(result)
