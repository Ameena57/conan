import os
import platform
from collections import OrderedDict, defaultdict

from jinja2 import Environment, FileSystemLoader

from conan import conan_version
from conan.internal.api import detect_api
from conan.tools.env.environment import ProfileEnvironment
from conans.client.loader import load_python_file
from conans.errors import ConanException, scoped_traceback
from conans.model.conf import ConfDefinition, CORE_CONF_PATTERN
from conans.model.options import Options
from conans.model.profile import Profile
from conans.model.recipe_ref import RecipeReference
from conans.paths import DEFAULT_PROFILE_NAME
from conans.util.config_parser import ConfigParser
from conans.util.files import mkdir, load_user_encoded


def _unquote(text):
    text = text.strip()
    if len(text) > 1 and (text[0] == text[-1]) and text[0] in "'\"":
        return text[1:-1]
    return text


_default_profile_plugin = """\
# This file was generated by Conan. Remove this comment if you edit this file or Conan
# will destroy your changes.

def profile_plugin(profile):
    settings = profile.settings
    if settings.get("compiler") in ("msvc", "clang") and settings.get("compiler.runtime"):
        if settings.get("compiler.runtime_type") is None:
            runtime = "Debug" if settings.get("build_type") == "Debug" else "Release"
            try:
                settings["compiler.runtime_type"] = runtime
            except ConanException:
                pass
    _check_correct_cppstd(settings)

def _check_correct_cppstd(settings):
    from conan.tools.scm import Version
    def _error(compiler, cppstd, min_version, version):
        from conan.errors import ConanException
        raise ConanException(f"The provided compiler.cppstd={cppstd} requires at least {compiler}"
                             f">={min_version} but version {version} provided")
    cppstd = settings.get("compiler.cppstd")
    version = settings.get("compiler.version")

    if cppstd and version:
        cppstd = cppstd.replace("gnu", "")
        version = Version(version)
        mver = None
        compiler = settings.get("compiler")
        if compiler == "gcc":
            mver = {"20": "8",
                    "17": "5",
                    "14": "4.8",
                    "11": "4.3"}.get(cppstd)
        elif compiler == "clang":
            mver = {"20": "6",
                    "17": "3.5",
                    "14": "3.4",
                    "11": "2.1"}.get(cppstd)
        elif compiler == "apple-clang":
            mver = {"20": "10",
                    "17": "6.1",
                    "14": "5.1",
                    "11": "4.5"}.get(cppstd)
        elif compiler == "msvc":
            mver = {"23": "193",
                    "20": "192",
                    "17": "191",
                    "14": "190"}.get(cppstd)
        if mver and version < mver:
            _error(compiler, cppstd, mver, version)
"""


class ProfileLoader:
    def __init__(self, cache):
        self._cache = cache

    def get_default_host(self):
        cache = self._cache

        default_profile = os.environ.get("CONAN_DEFAULT_PROFILE")
        if default_profile is None:
            default_profile = cache.new_config.get("core:default_profile", default=DEFAULT_PROFILE_NAME)

        default_profile = os.path.join(cache.profiles_path, default_profile)
        if not os.path.exists(default_profile):
            msg = ("The default host profile '{}' doesn't exist.\n"
                   "You need to create a default profile (type 'conan profile detect' command)\n"
                   "or specify your own profile with '--profile:host=<myprofile>'")
            # TODO: Add detailed instructions when cli is improved
            raise ConanException(msg.format(default_profile))
        return default_profile

    def get_default_build(self):
        cache = self._cache
        default_profile = cache.new_config.get("core:default_build_profile", default=DEFAULT_PROFILE_NAME)
        default_profile = os.path.join(cache.profiles_path, default_profile)
        if not os.path.exists(default_profile):
            msg = ("The default build profile '{}' doesn't exist.\n"
                   "You need to create a default profile (type 'conan profile detect' command)\n"
                   "or specify your own profile with '--profile:build=<myprofile>'")
            # TODO: Add detailed instructions when cli is improved
            raise ConanException(msg.format(default_profile))
        return default_profile

    def _load_profile_plugin(self):
        profile_plugin = os.path.join(self._cache.plugins_path, "profile.py")
        if not os.path.exists(profile_plugin):
            raise ConanException("The 'profile.py' plugin file doesn't exist. If you want "
                                 "to disable it, edit its contents instead of removing it")

        mod, _ = load_python_file(profile_plugin)
        if hasattr(mod, "profile_plugin"):
            return mod.profile_plugin

    def from_cli_args(self, profiles, settings, options, conf, cwd):
        """ Return a Profile object, as the result of merging a potentially existing Profile
        file and the args command-line arguments
        """
        if conf and any(CORE_CONF_PATTERN.match(c) for c in conf):
            raise ConanException("[conf] 'core.*' configurations are not allowed in profiles.")

        result = Profile()
        for p in profiles:
            tmp = self.load_profile(p, cwd)
            result.compose_profile(tmp)

        args_profile = _profile_parse_args(settings, options, conf)
        result.compose_profile(args_profile)
        # Only after everything has been aggregated, try to complete missing settings
        profile_plugin = self._load_profile_plugin()
        if profile_plugin is not None:
            try:
                profile_plugin(result)
            except Exception as e:
                msg = f"Error while processing 'profile.py' plugin"
                msg = scoped_traceback(msg, e, scope="/extensions/plugins")
                raise ConanException(msg)
        result.process_settings(self._cache)
        return result

    def load_profile(self, profile_name, cwd=None):
        # TODO: This can be made private, only used in testing now
        cwd = cwd or os.getcwd()
        profile = self._load_profile(profile_name, cwd)
        return profile

    def _load_profile(self, profile_name, cwd):
        """ Will look for "profile_name" in disk if profile_name is absolute path,
        in current folder if path is relative or in the default folder otherwise.
        return: a Profile object
        """

        profile_path = self.get_profile_path(profile_name, cwd)
        try:
            text = load_user_encoded(profile_path)
        except Exception as e:
            raise ConanException(f"Cannot load profile:\n{e}")

        # All profiles will be now rendered with jinja2 as first pass
        base_path = os.path.dirname(profile_path)
        file_path = os.path.basename(profile_path)
        context = {"platform": platform,
                   "os": os,
                   "profile_dir": base_path,
                   "profile_name": file_path,
                   "conan_version": conan_version,
                   "detect_api": detect_api}
        rtemplate = Environment(loader=FileSystemLoader(base_path)).from_string(text)
        text = rtemplate.render(context)

        try:
            return self._recurse_load_profile(text, profile_path)
        except ConanException as exc:
            raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))

    def _recurse_load_profile(self, text, profile_path):
        """ Parse and return a Profile object from a text config like representation.
            cwd is needed to be able to load the includes
        """
        try:
            inherited_profile = Profile()
            cwd = os.path.dirname(os.path.abspath(profile_path)) if profile_path else None
            profile_parser = _ProfileParser(text)
            # Iterate the includes and call recursive to get the profile and variables
            # from parent profiles
            for include in profile_parser.includes:
                # Recursion !!
                profile = self._load_profile(include, cwd)
                inherited_profile.compose_profile(profile)

            # Current profile before update with parents (but parent variables already applied)
            inherited_profile = _ProfileValueParser.get_profile(profile_parser.profile_text,
                                                                inherited_profile)
            return inherited_profile
        except ConanException:
            raise
        except Exception as exc:
            raise ConanException("Error parsing the profile text file: %s" % str(exc))

    def get_profile_path(self, profile_name, cwd, exists=True):

        def valid_path(_profile_path, _profile_name=None):
            if exists and not os.path.isfile(_profile_path):
                raise ConanException("Profile not found: {}".format(_profile_name or _profile_path))
            return _profile_path

        if os.path.isabs(profile_name):
            return valid_path(profile_name)

        if profile_name[:2] in ("./", ".\\") or profile_name.startswith(".."):  # local
            profile_path = os.path.abspath(os.path.join(cwd, profile_name))
            return valid_path(profile_path, profile_name)

        default_folder = self._cache.profiles_path
        if not os.path.exists(default_folder):
            mkdir(default_folder)
        profile_path = os.path.join(default_folder, profile_name)
        if exists:
            if not os.path.isfile(profile_path):
                profile_path = os.path.abspath(os.path.join(cwd, profile_name))
            if not os.path.isfile(profile_path):
                raise ConanException("Profile not found: %s" % profile_name)
        return profile_path


# TODO: This class can be removed/simplified now to a function, it reduced to just __init__
class _ProfileParser:

    def __init__(self, text):
        """ divides the text in 3 items:
        - self.includes: List of other profiles to include
        - self.profile_text: the remaining, containing settings, options, env, etc
        """
        self.includes = []
        self.profile_text = ""

        for counter, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("["):
                self.profile_text = "\n".join(text.splitlines()[counter:])
                break
            elif line.startswith("include("):
                include = line.split("include(", 1)[1]
                if not include.endswith(")"):
                    raise ConanException("Invalid include statement")
                include = include[:-1]
                self.includes.append(include)
            else:
                raise ConanException("Error while parsing line %i: '%s'" % (counter, line))


class _ProfileValueParser(object):
    """ parses a "pure" or "effective" profile, with no includes, no variables,
    as the one in the lockfiles, or once these things have been processed by ProfileParser
    """
    @staticmethod
    def get_profile(profile_text, base_profile=None):
        # Trying to strip comments might be problematic if things contain #
        doc = ConfigParser(profile_text, allowed_fields=["tool_requires", "system_tools",
                                                         "system_deps", "settings",
                                                         "options", "conf", "buildenv", "runenv"])

        # Parse doc sections into Conan model, Settings, Options, etc
        settings, package_settings = _ProfileValueParser._parse_settings(doc)
        options = Options.loads(doc.options) if doc.options else None
        tool_requires = _ProfileValueParser._parse_tool_requires(doc)

        if doc.system_tools:
            system_tools = [RecipeReference.loads(r) for r in doc.system_tools.splitlines()]
        else:
            system_tools = []

        system_deps = {}
        if doc.system_deps:
            for r in doc.system_deps.splitlines():
                tokens = r.split(":", 1)
                if len(tokens) == 2:
                    src, target = tokens
                    target = RecipeReference.loads(target.strip())
                else:
                    src, target = r, None
                system_deps[RecipeReference.loads(src.strip())] = target

        if doc.conf:
            conf = ConfDefinition()
            conf.loads(doc.conf, profile=True)
        else:
            conf = None
        buildenv = ProfileEnvironment.loads(doc.buildenv) if doc.buildenv else None
        runenv = ProfileEnvironment.loads(doc.runenv) if doc.runenv else None

        # Create or update the profile
        base_profile = base_profile or Profile()
        current_system_tools = {r.name: r for r in base_profile.system_tools}
        current_system_tools.update({r.name: r for r in system_tools})
        base_profile.system_tools = list(current_system_tools.values())
        base_profile.system_deps.update(system_deps)

        base_profile.settings.update(settings)
        for pkg_name, values_dict in package_settings.items():
            base_profile.package_settings[pkg_name].update(values_dict)
        for pattern, refs in tool_requires.items():
            # If the same package, different version is added, the latest version prevail
            current = base_profile.tool_requires.setdefault(pattern, [])
            current_dict = {r.name: r for r in current}
            current_dict.update({r.name: r for r in refs})
            current[:] = list(current_dict.values())
        if options is not None:
            base_profile.options.update_options(options)
        if conf is not None:
            base_profile.conf.update_conf_definition(conf)
        if buildenv is not None:
            base_profile.buildenv.update_profile_env(buildenv)
        if runenv is not None:
            base_profile.runenv.update_profile_env(runenv)
        return base_profile

    @staticmethod
    def _parse_tool_requires(doc):
        result = OrderedDict()
        if doc.tool_requires:
            # FIXME CHECKS OF DUPLICATED?
            for br_line in doc.tool_requires.splitlines():
                tokens = br_line.split(":", 1)
                if len(tokens) == 1:
                    pattern, req_list = "*", br_line
                else:
                    pattern, req_list = tokens
                refs = [RecipeReference.loads(r.strip()) for r in req_list.split(",")]
                result.setdefault(pattern, []).extend(refs)
        return result

    @staticmethod
    def _parse_settings(doc):
        def get_package_name_value(item):
            """Parse items like package:name=value or name=value"""
            packagename = None
            if ":" in item:
                tmp = item.split(":", 1)
                packagename, item = tmp

            result_name, result_value = item.split("=", 1)
            result_name = result_name.strip()
            result_value = _unquote(result_value)
            return packagename, result_name, result_value

        package_settings = OrderedDict()
        settings = OrderedDict()
        for setting in doc.settings.splitlines():
            setting = setting.strip()
            if not setting or setting.startswith("#"):
                continue
            if "=" not in setting:
                raise ConanException("Invalid setting line '%s'" % setting)
            package_name, name, value = get_package_name_value(setting)
            if package_name:
                package_settings.setdefault(package_name, OrderedDict())[name] = value
            else:
                settings[name] = value
        return settings, package_settings


def _profile_parse_args(settings, options, conf):
    """ return a Profile object result of parsing raw data
    """
    def _get_tuples_list_from_extender_arg(items):
        if not items:
            return []
        # Validate the pairs
        for item in items:
            chunks = item.split("=", 1)
            if len(chunks) != 2:
                raise ConanException("Invalid input '%s', use 'name=value'" % item)
        return [(item[0], item[1]) for item in [item.split("=", 1) for item in items]]

    def _get_simple_and_package_tuples(items):
        """Parse items like "thing:item=value or item2=value2 and returns a tuple list for
        the simple items (name, value) and a dict for the package items
        {package: [(item, value)...)], ...}
        """
        simple_items = []
        package_items = defaultdict(list)
        tuples = _get_tuples_list_from_extender_arg(items)
        for name, value in tuples:
            if ":" in name:  # Scoped items
                tmp = name.split(":", 1)
                ref_name = tmp[0]
                name = tmp[1]
                package_items[ref_name].append((name, value))
            else:
                simple_items.append((name, value))
        return simple_items, package_items

    settings, package_settings = _get_simple_and_package_tuples(settings)

    result = Profile()
    result.options = Options.loads("\n".join(options or []))
    result.settings = OrderedDict(settings)
    if conf:
        result.conf = ConfDefinition()
        result.conf.loads("\n".join(conf))

    for pkg, values in package_settings.items():
        result.package_settings[pkg] = OrderedDict(values)

    return result


def migrate_profile_plugin(cache):
    from conans.client.migrations import update_file

    profile_plugin_file = os.path.join(cache.plugins_path, "profile.py")
    update_file(profile_plugin_file, _default_profile_plugin)
