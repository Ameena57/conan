import fnmatch
from collections import OrderedDict

from conans.errors import ConanException


BUILT_IN_CONFS = {
    "core:required_conan_version": (str, "Raise if current version does not match the defined range."),
    "core.package_id:msvc_visual_incompatible": (str, "Allows opting-out the fallback from the new msvc compiler to the Visual Studio compiler existing binaries"),
    "core:default_profile": (str, "Defines the default host profile ('default' by default)"),
    "core:default_build_profile": (str, "Defines the default build profile (None by default)"),
    "tools.android:ndk_path": (str, "Argument for the CMAKE_ANDROID_NDK"),
    "tools.build:skip_test": (str, "Do not execute CMake.test() and Meson.test() when enabled"),
    "tools.build:jobs": (str, "Default compile jobs number -jX Ninja, Make, /MP VS (default: max CPUs)"),
    "tools.cmake.cmaketoolchain:generator": (str, "User defined CMake generator to use instead of default"),
    "tools.cmake.cmaketoolchain:find_package_prefer_config": (str, "Argument for the CMAKE_FIND_PACKAGE_PREFER_CONFIG"),
    "tools.cmake.cmaketoolchain:toolchain_file": (str, "Use other existing file rather than conan_toolchain.cmake one"),
    "tools.cmake.cmaketoolchain:user_toolchain": (str, "Inject existing user toolchain at the beginning of conan_toolchain.cmake"),
    "tools.cmake.cmaketoolchain:system_name": (str, "Define CMAKE_SYSTEM_NAME in CMakeToolchain"),
    "tools.cmake.cmaketoolchain:system_version": (str, "Define CMAKE_SYSTEM_VERSION in CMakeToolchain"),
    "tools.cmake.cmaketoolchain:system_processor": (str, "Define CMAKE_SYSTEM_PROCESSOR in CMakeToolchain"),
    "tools.env.virtualenv:auto_use": (str, "Automatically activate virtualenv file generation"),
    "tools.files.download:retry": (str, "Number of retries in case of failure when downloading"),
    "tools.files.download:retry_wait": (str, "Seconds to wait between download attempts"),
    "tools.gnu:make_program": (str, "Indicate path to make program"),
    "tools.gnu:define_libcxx11_abi": (str, "Force definition of GLIBCXX_USE_CXX11_ABI=1 for libstdc++11"),
    "tools.google.bazel:config": (str, "Define Bazel config file"),
    "tools.google.bazel:bazelrc_path": (str, "Defines Bazel rc-path"),
    "tools.microsoft.msbuild:verbosity": (str, "Verbosity level for MSBuild: 'Quiet', 'Minimal', 'Normal', 'Detailed', 'Diagnostic'"),
    "tools.microsoft.msbuild:vs_version": (str, "Defines the IDE version when using the new msvc compiler"),
    "tools.microsoft.msbuild:max_cpu_count": (str, "Argument for the /m when running msvc to build parallel projects"),
    "tools.microsoft.msbuild:installation_path": (str, "VS install path, to avoid auto-detect via vswhere, like C:/Program Files (x86)/Microsoft Visual Studio/2019/Community"),
    "tools.microsoft.msbuilddeps:exclude_code_analysis": (str, "Suppress MSBuild code analysis for patterns"),
    "tools.microsoft.msbuildtoolchain:compile_options": (str, "Dictionary with MSBuild compiler options"),
    "tools.intel:installation_path": (str, "Defines the Intel oneAPI installation root path"),
    "tools.intel:setvars_args": (str, "Custom arguments to be passed onto the setvars.sh|bat script from Intel oneAPI"),
    "tools.system.package_manager:tool": (str, "Default package manager tool: 'apt-get', 'yum', 'dnf', 'brew', 'pacman', 'choco', 'zypper', 'pkg' or 'pkgutil'"),
    "tools.system.package_manager:mode": (str, "Mode for package_manager tools: 'check' or 'install'"),
    "tools.system.package_manager:sudo": (str, "Use 'sudo' when invoking the package manager tools in Linux (False by default)"),
    "tools.system.package_manager:sudo_askpass": (str, "Use the '-A' argument if using sudo in Linux to invoke the system package manager (False by default)"),
}


def _is_profile_module(module_name):
    # These are the modules that are propagated to profiles and user recipes
    _user_modules = "tools.", "user."
    return any(module_name.startswith(user_module) for user_module in _user_modules)


# FIXME: Refactor all the next classes because they are mostly the same as
#        conan.tools.env.environment ones
class _ConfVarPlaceHolder:
    pass


class _ConfValue:

    def __init__(self, name, value):
        self._name = name
        self._value = value

    def __repr__(self):
        return repr(self._value)

    @property
    def value(self):
        return self._value

    def copy(self):
        return self.__class__(self._name, self._value)

    def dumps(self):
        raise NotImplementedError

    def remove(self, value):
        raise NotImplementedError

    def append(self, value):
        raise NotImplementedError

    def prepend(self, value):
        raise NotImplementedError

    def compose_conf_value(self, other):
        raise NotImplementedError


class _ConfStrValue(_ConfValue):

    def __init__(self, name, value):
        value = None if value is None else str(value).strip()
        super(_ConfStrValue, self).__init__(name, value)

    def dumps(self):
        if self._value is None:
            return "{}=!".format(self._name)  # unset
        else:
            return "{}={}".format(self._name, self._value)

    def remove(self, value):
        self._value = ""

    def append(self, value):
        raise ConanException("str values cannot append other values.")

    def prepend(self, value):
        raise ConanException("str values cannot prepend other values.")

    def compose_conf_value(self, other):
        pass


class _ConfListValue(_ConfValue):

    def __init__(self, name, value):
        value = [] if value is None else value if isinstance(value, list) else [value]
        super(_ConfListValue, self).__init__(name, value)

    def dumps(self):
        result = []
        if not self._value:  # Empty means unset
            result.append("{}=!".format(self._name))
        elif _ConfVarPlaceHolder in self._value:
            index = self._value.index(_ConfVarPlaceHolder)
            for v in self._value[:index]:
                result.append("{}=+{}".format(self._name, v))
            for v in self._value[index+1:]:
                result.append("{}+={}".format(self._name, v))
        else:
            append = ""
            for v in self._value:
                result.append("{}{}={}".format(self._name, append, v))
                append = "+"
        return "\n".join(result)

    def remove(self, value):
        self._value.remove(value)

    def append(self, value):
        if isinstance(value, list):
            self._value.extend(value)
        else:
            self._value.append(value)

    def prepend(self, value):
        if isinstance(value, list):
            self._value = value + self._value
        else:
            self._value.insert(0, value)

    def compose_conf_value(self, other):
        """
        self has precedence, the "other" will add/append if possible and not conflicting, but
        self mandates what to do. If self has define(), without placeholder, that will remain.
        :type other: _ConfValue
        """
        try:
            index = self._value.index(_ConfVarPlaceHolder)
        except ValueError:  # It doesn't have placeholder
            pass
        else:
            new_value = self._value[:]  # do a copy
            new_value[index:index + 1] = other._value  # replace the placeholder
            self._value = new_value


class Conf:

    def __init__(self):
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def __bool__(self):
        return bool(self._values)

    __nonzero__ = __bool__

    def __repr__(self):
        return "Conf: " + repr(self._values)

    def __eq__(self, other):
        """
        :type other: Conf
        """
        return other._values == self._values

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0. Use self.get() instead.
        """
        # FIXME: Keeping backward compatibility
        return self.get(name)

    def __setitem__(self, name, value):
        """
        DEPRECATED: it's going to disappear in Conan 2.0.
        """
        # FIXME: Keeping backward compatibility
        self.define(name, value)  # it's like a new definition

    def __delitem__(self, name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0.
        """
        # FIXME: Keeping backward compatibility
        self.pop(name)

    def items(self):
        # FIXME: Keeping backward compatibility
        for k, v in self._values.items():
            yield k, v.value

    @property
    def sha(self):
        # FIXME: Keeping backward compatibility
        return self.dumps()

    def get(self, conf_name, default=None):
        """
        Get all the values belonging to the passed conf name. By default, those values
        will be returned as a str-like object.
        """
        conf_value = self._values.get(conf_name)
        if conf_value:
            return conf_value.value
        else:
            return default

    def pop(self, conf_name, default=None):
        """
        Remove any key-value given the conf name
        """
        value = self.get(conf_name, default)
        self._values.pop(conf_name, None)
        return value

    def _get_conf_value(self, name, value):
        """
        Get a valid _ConfValue object based on the built-in Conf type declared
        or the value-like object. For now, we only manage lists or strings.
        """
        type_ = BUILT_IN_CONFS.get(name, [None])[0]
        if type_ is list or isinstance(value, list) \
           or isinstance(self._values.get(name), _ConfListValue):
            return _ConfListValue(name, value)
        else:
            # Any other value will be converted to string by default
            return _ConfStrValue(name, value)

    @staticmethod
    def _validate_lower_case(name):
        if name != name.lower():
            raise ConanException("Conf '{}' must be lowercase".format(name))

    def copy(self):
        c = Conf()
        c._values = self._values.copy()
        return c

    def dumps(self):
        """ returns a string with a profile-like original definition, not the full environment
        values
        """
        return "\n".join([v.dumps() for v in reversed(self._values.values())])

    def define(self, name, value):
        self._validate_lower_case(name)
        self._values[name] = self._get_conf_value(name, value)

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=
        """
        self._values[name] = self._get_conf_value(name, None)

    def append(self, name, value):
        self._validate_lower_case(name)
        conf_value = self._get_conf_value(name, [_ConfVarPlaceHolder])
        self._values.setdefault(name, conf_value).append(value)

    def prepend(self, name, value):
        self._validate_lower_case(name)
        conf_value = self._get_conf_value(name, [_ConfVarPlaceHolder])
        self._values.setdefault(name, conf_value).prepend(value)

    def remove(self, name, value):
        self._values[name].remove(value)

    def compose_conf(self, other):
        """
        :param other: other has less priority than current one
        :type other: Conf
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v.copy()
            else:
                existing.compose_conf_value(v)
        return self

    def filter_user_modules(self):
        result = Conf()
        for k, v in self._values.items():
            if _is_profile_module(k):
                result._values[k] = v
        return result


class ConfDefinition:

    actions = (("+=", "append"), ("=+", "prepend"),
               ("=!", "unset"), ("=", "define"))

    def __init__(self):
        self._pattern_confs = OrderedDict()

    def __repr__(self):
        return "ConfDefinition: " + repr(self._pattern_confs)

    def __bool__(self):
        return bool(self._pattern_confs)

    __nonzero__ = __bool__

    def __getitem__(self, module_name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0. Use self.get() instead.
        if a module name is requested for this, it goes to the None-Global config by default
        """
        pattern, name = self._split_pattern_name(module_name)
        return self._pattern_confs.get(pattern, Conf()).get(name)

    def __delitem__(self, module_name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0.  Use self.pop() instead.
        if a module name is requested for this, it goes to the None-Global config by default
        """
        pattern, name = self._split_pattern_name(module_name)
        self._pattern_confs.get(pattern, Conf()).pop(name)

    def get(self, conf_name, default=None):
        """
        Get the value of the  conf name requested and convert it to the [type]-like passed.
        """
        pattern, name = self._split_pattern_name(conf_name)
        return self._pattern_confs.get(pattern, Conf()).get(name, default=default)

    def pop(self, conf_name, default=None):
        """
        Remove the conf name passed.
        """
        pattern, name = self._split_pattern_name(conf_name)
        return self._pattern_confs.get(pattern, Conf()).pop(name, default=default)

    @staticmethod
    def _split_pattern_name(pattern_name):
        if pattern_name.count(":") >= 2:
            pattern, name = pattern_name.split(":", 1)
        else:
            pattern, name = None, pattern_name
        return pattern, name

    def get_conanfile_conf(self, ref):
        """ computes package-specific Conf
        it is only called when conanfile.buildenv is called
        the last one found in the profile file has top priority
        """
        result = Conf()
        for pattern, conf in self._pattern_confs.items():
            if pattern is None or fnmatch.fnmatch(str(ref), pattern):
                # Latest declared has priority, copy() necessary to not destroy data
                result = conf.copy().compose_conf(result)
        return result

    def update_conf_definition(self, other):
        """
        :type other: ConfDefinition
        :param other: The argument profile has priority/precedence over the current one.
        """
        for pattern, conf in other._pattern_confs.items():
            self._update_conf_definition(pattern, conf)

    def _update_conf_definition(self, pattern, conf):
        existing = self._pattern_confs.get(pattern)
        if existing:
            self._pattern_confs[pattern] = conf.compose_conf(existing)
        else:
            self._pattern_confs[pattern] = conf

    def rebase_conf_definition(self, other):
        """
        for taking the new global.conf and composing with the profile [conf]
        :type other: ConfDefinition
        """
        for pattern, conf in other._pattern_confs.items():
            new_conf = conf.filter_user_modules()  # Creates a copy, filtered
            existing = self._pattern_confs.get(pattern)
            if existing:
                existing.compose_conf(new_conf)
            else:
                self._pattern_confs[pattern] = new_conf

    def update(self, key, value, profile=False, method="define"):
        """
        Define/append/prepend/unset any Conf line
        >> update("tools.microsoft.msbuild:verbosity", "Detailed")
        """
        pattern, name = self._split_pattern_name(key)

        if not _is_profile_module(name):
            if profile:
                raise ConanException("[conf] '{}' not allowed in profiles".format(key))
            if pattern is not None:
                raise ConanException("Conf '{}' cannot have a package pattern".format(key))

        # strip whitespaces before/after =
        # values are not strip() unless they are a path, to preserve potential whitespaces
        name = name.strip()

        # When loading from profile file, latest line has priority
        conf = Conf()
        if method == "unset":
            conf.unset(name)
        else:
            getattr(conf, method)(name, value)
        # Update
        self._update_conf_definition(pattern, conf)

    def as_list(self):
        result = []
        for pattern, conf in self._pattern_confs.items():
            for name, value in sorted(conf.items()):
                if pattern:
                    result.append(("{}:{}".format(pattern, name), value))
                else:
                    result.append((name, value))
        return result

    def dumps(self):
        result = []
        for pattern, conf in self._pattern_confs.items():
            if pattern is None:
                result.append(conf.dumps())
            else:
                result.append("\n".join("{}:{}".format(pattern, line) if line else ""
                                        for line in conf.dumps().splitlines()))
        if result:
            result.append("")
        return "\n".join(result)

    def loads(self, text, profile=False):
        self._pattern_confs = {}

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for op, method in ConfDefinition.actions:
                tokens = line.split(op, 1)
                if len(tokens) != 2:
                    continue

                pattern_name, value = tokens
                try:
                    parsed_value = eval(value)
                except:
                    parsed_value = value.strip()

                self.update(pattern_name, parsed_value, profile=profile, method=method)
                break
            else:
                raise ConanException("Bad conf definition: {}".format(line))
