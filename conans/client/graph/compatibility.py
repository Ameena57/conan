import os
from collections import OrderedDict

from conan.internal.cache.home_paths import HomePaths
from conans.client.graph.compute_pid import run_validate_package_id
from conans.client.loader import load_python_file
from conans.errors import conanfile_exception_formatter, ConanException, scoped_traceback

# TODO: Define other compatibility besides applications
_default_compat = """\
# This file was generated by Conan. Remove this comment if you edit this file or Conan
# will destroy your changes.
from cppstd_compat import cppstd_compat


def compatibility(conanfile):
    configs = cppstd_compat(conanfile)
    # TODO: Append more configurations for your custom compatibility rules
    return configs
"""


_default_cppstd_compat = """\
# This file was generated by Conan. Remove this comment if you edit this file or Conan
# will destroy your changes.
from conan.tools.build import supported_cppstd
from conan.errors import ConanException


def cppstd_compat(conanfile):
    # It will try to find packages with all the cppstd versions
    extension_properties = getattr(conanfile, "extension_properties", {})
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    cppstd = conanfile.settings.get_safe("compiler.cppstd")
    if not compiler or not compiler_version:
        return []
    base = dict(conanfile.settings.values_list)
    factors = []  # List of list, each sublist is a potential combination
    if cppstd is not None and extension_properties.get("compatibility_cppstd") is not False:
        cppstd_possible_values = supported_cppstd(conanfile)
        if cppstd_possible_values is None:
            conanfile.output.warning(f'No cppstd compatibility defined for compiler "{compiler}"')
        else:
            factors.append([{"compiler.cppstd": v} for v in cppstd_possible_values if v != cppstd])

    if compiler == "msvc":
        msvc_fallback = {"194": "193"}.get(compiler_version)
        if msvc_fallback:
            factors.append([{"compiler.version": msvc_fallback}])

    conanfile.output.info(f"FACTORS {factors}")
    combinations = []
    for factor in factors:
        if not combinations:
            combinations = factor
            continue
        new_combinations = []
        for comb in combinations:
            for f in factor:
                comb = comb.copy()
                comb.update(f)
                new_combinations.append(comb)
        combinations = new_combinations

    conanfile.output.info(f"COMbINATIONS {combinations}")
    ret = []
    for comb in combinations:
        configuration = base.copy()
        configuration.update(comb)
        ret.append({"settings": [(k, v) for k, v in configuration.items()]})
    return ret
"""


def migrate_compatibility_files(cache_folder):
    from conans.client.migrations import update_file
    compatible_folder = HomePaths(cache_folder).compatibility_plugin_path
    compatibility_file = os.path.join(compatible_folder, "compatibility.py")
    cppstd_compat_file = os.path.join(compatible_folder, "cppstd_compat.py")
    update_file(compatibility_file, _default_compat)
    update_file(cppstd_compat_file, _default_cppstd_compat)


class BinaryCompatibility:

    def __init__(self, compatibility_plugin_folder):
        compatibility_file = os.path.join(compatibility_plugin_folder, "compatibility.py")
        if not os.path.exists(compatibility_file):
            raise ConanException("The 'compatibility.py' plugin file doesn't exist. If you want "
                                 "to disable it, edit its contents instead of removing it")
        mod, _ = load_python_file(compatibility_file)
        self._compatibility = mod.compatibility

    def compatibles(self, conanfile):
        compat_infos = []
        if hasattr(conanfile, "compatibility"):
            with conanfile_exception_formatter(conanfile, "compatibility"):
                recipe_compatibles = conanfile.compatibility()
                compat_infos.extend(self._compatible_infos(conanfile, recipe_compatibles))

        try:
            plugin_compatibles = self._compatibility(conanfile)
        except Exception as e:
            msg = f"Error while processing 'compatibility.py' plugin for '{conanfile}'"
            msg = scoped_traceback(msg, e, scope="plugins/compatibility")
            raise ConanException(msg)
        compat_infos.extend(self._compatible_infos(conanfile, plugin_compatibles))
        if not compat_infos:
            return {}

        result = OrderedDict()
        original_info = conanfile.info
        original_settings = conanfile.settings
        original_settings_target = conanfile.settings_target
        original_options = conanfile.options
        for c in compat_infos:
            # we replace the conanfile, so ``validate()`` and ``package_id()`` can
            # use the compatible ones
            conanfile.info = c
            conanfile.settings = c.settings
            conanfile.settings_target = c.settings_target
            conanfile.options = c.options
            run_validate_package_id(conanfile)
            pid = c.package_id()
            if pid not in result and not c.invalid:
                result[pid] = c
        # Restore the original state
        conanfile.info = original_info
        conanfile.settings = original_settings
        conanfile.settings_target = original_settings_target
        conanfile.options = original_options
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
                settings_target = elem.get("settings_target")
                if settings_target and compat_info.settings_target:
                    compat_info.settings_target.update_values(settings_target)
        return result
