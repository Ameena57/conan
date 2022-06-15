import os
from collections import OrderedDict

from conans.client.graph.compute_pid import run_validate_package_id
from conans.client.loader import load_python_file
from conans.errors import conanfile_exception_formatter
from conans.util.files import save

# TODO: Define other compatibility besides applications
_default_compat = """\
# This file was generated by Conan. Remove this comment if you edit this file or Conan
# will destroy your changes.
from app_compat import app_compat
from cppstd_compat import cppstd_compat


def compatibility(conanfile):
    if conanfile.package_type == "application":
        return app_compat(conanfile)

    configs = cppstd_compat(conanfile)
    # TODO: Append more configurations for your custom compatibility rules
    return configs
"""


_default_cppstd_compat = """\
# This file was generated by Conan. Remove this comment if you edit this file or Conan
# will destroy your changes.
from conan.tools.build import supported_cppstd


def cppstd_compat(conanfile):
    # It will try to find packages with all the cppstd versions

    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    cppstd = conanfile.settings.get_safe("compiler.cppstd")
    if not compiler or not compiler_version or not cppstd:
        return []
    base = dict(conanfile.settings.values_list)
    cppstd_possible_values = supported_cppstd(conanfile)
    ret = []
    for _cppstd in cppstd_possible_values:
        if _cppstd is None or _cppstd == cppstd:
            continue
        configuration = base.copy()
        configuration["compiler.cppstd"] = _cppstd
        ret.append({"settings": [(k, v) for k, v in configuration.items()]})

    return ret
"""


_default_app_compat = """\
# This file was generated by Conan. Remove this comment if you edit this file or Conan
# will destroy your changes.
from conan.tools.build import default_cppstd

def app_compat(conanfile):
    # Will try to find a binary for the latest compiler version. In case it is not defined
    # os, and arch should be at least defined.
    os_ = conanfile.settings.get_safe("os")
    arch = conanfile.settings.get_safe("arch")
    if os_ is None or arch is None:
        return

    compiler = conanfile.settings.get_safe("compiler")
    compiler = compiler or {"Windows": "msvc", "Macos": "apple-clang"}.get(os_, "gcc")
    configuration = {"compiler": compiler}

    compiler_version = conanfile.settings.get_safe("compiler.version")
    if not compiler_version:
        # Latest compiler version
        definition = conanfile.settings.get_definition()
        compiler_versions = definition["compiler"][compiler]["version"]
        compiler_version = compiler_versions[-1] # Latest

    configuration["compiler.version"] = compiler_version

    build_type = conanfile.settings.get_safe("build_type")
    configuration["build_type"] = build_type or "Release"

    if compiler == "msvc":
        runtime = conanfile.settings.get_safe("compiler.runtime")
        if runtime is None:
            configuration["compiler.runtime"] = "dynamic"
            configuration["compiler.runtime_type"] = configuration["build_type"]

    configuration["compiler.cppstd"] = conanfile.settings.get_safe("compiler.cppstd") or default_cppstd(conanfile, compiler, compiler_version)
    return [{"settings": [(k, v) for k, v in configuration.items()]}]
"""


def get_binary_compatibility_file_paths(cache):
    compatible_folder = os.path.join(cache.plugins_path, "compatibility")
    compatibility_file = os.path.join(compatible_folder, "compatibility.py")
    app_compat_file = os.path.join(compatible_folder, "app_compat.py")
    cppstd_compat_file = os.path.join(compatible_folder, "cppstd_compat.py")
    return compatibility_file, app_compat_file, cppstd_compat_file


def migrate_compatibility_files(cache):
    from conans.client.migrations import update_file

    compatibility_file, app_compat_file, cppstd_compat_file = get_binary_compatibility_file_paths(cache)
    update_file(compatibility_file, _default_compat)
    update_file(app_compat_file, _default_app_compat)
    update_file(cppstd_compat_file, _default_cppstd_compat)


class BinaryCompatibility:

    def __init__(self, cache):
        compatibility_file, app_compat_file, cppstd_compat_file = get_binary_compatibility_file_paths(cache)
        mod, _ = load_python_file(compatibility_file)
        self._compatibility = mod.compatibility

    def compatibles(self, conanfile):
        compat_infos = []
        if hasattr(conanfile, "compatibility"):
            with conanfile_exception_formatter(conanfile, "compatibility"):
                recipe_compatibles = conanfile.compatibility()
                compat_infos.extend(self._compatible_infos(conanfile, recipe_compatibles))

        plugin_compatibles = self._compatibility(conanfile)
        compat_infos.extend(self._compatible_infos(conanfile, plugin_compatibles))
        if not compat_infos:
            return {}

        result = OrderedDict()
        original_info = conanfile.info
        for c in compat_infos:
            conanfile.info = c
            run_validate_package_id(conanfile)
            pid = c.package_id()
            if pid not in result and not c.invalid:
                result[pid] = c
        # Restore the original state
        conanfile.info = original_info
        return result

    @staticmethod
    def _compatible_infos(conanfile, compatibles):
        result = []
        if compatibles:
            for elem in compatibles:
                compat_info = conanfile.original_info.clone()
                settings = elem.get("settings")
                if settings:
                    compat_info.settings.update_values(settings)
                options = elem.get("options")
                if options:
                    compat_info.options.update(options_values=OrderedDict(options))
                result.append(compat_info)
        return result
