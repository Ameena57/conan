import os
import textwrap
from collections import namedtuple

from jinja2 import Template, StrictUndefined

from conan.errors import ConanException
from conans.util.files import save


_DepInfo = namedtuple("DepInfo", ['name', 'requires', 'cpp_info'])
_LibInfo = namedtuple("LibInfo", ['name', 'is_shared', 'lib_path', 'interface_path'])


def _get_name_with_namespace(namespace, name):
    """
    Build a name with a namespace, e.g., openssl-crypto
    """
    return f"{namespace}-{name}"


def _get_package_reference_name(dep):
    """
    Get the reference name for the given package
    """
    return dep.ref.name


def _get_package_name(dep):
    pkg_name = dep.cpp_info.get_property("bazel_module_name") or _get_package_reference_name(dep)
    return pkg_name


def _get_component_name(dep, comp_ref_name):
    pkg_name = _get_package_name(dep)
    if comp_ref_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if _get_package_reference_name(dep) == comp_ref_name:
            return pkg_name
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_ref_name))
    comp_name = dep.cpp_info.components[comp_ref_name].get_property("bazel_module_name")
    # If user did not set bazel_module_name, let's create a component name
    # with a namespace, e.g., dep-comp1
    return comp_name or _get_name_with_namespace(pkg_name, comp_ref_name)


# FIXME: This function should be a common one to be used by PkgConfigDeps, CMakeDeps?, etc.
def get_requirements(conanfile, build_context_activated):
    """
    Simply save the activated requirements (host + build + test), and the deactivated ones
    """
    # All the requirements
    host_req = conanfile.dependencies.host
    build_req = conanfile.dependencies.build  # tool_requires
    test_req = conanfile.dependencies.test

    for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
        # Require is not used at the moment, but its information could be used,
        # and will be used in Conan 2.0
        # Filter the build_requires not activated with self.build_context_activated
        if require.build and dep.ref.name not in build_context_activated:
            continue
        yield require, dep


def _get_libs(conanfile, cpp_info, is_shared=False, relative_to_path=None) -> list:
    """
    Get the static/shared library paths

    :param conanfile: The current recipe object.
    :param dep: <ConanFileInterface obj> of the dependency.
    :param cpp_info: <CppInfo obj> of the component.
    :param relative_to_path: base path to prune from each library path
    :return: dict of static/shared library absolute paths ->
             {lib_name: (IS_SHARED, LIB_PATH, DLL_PATH)}
             Note: LIB_PATH could be both static and shared ones in case of UNIX. If Windows it'll be
                   the interface library xxx.lib linked to the DLL_PATH one.
    """
    cpp_info = cpp_info
    libdirs = cpp_info.libdirs
    bindirs = cpp_info.bindirs
    libs = cpp_info.libs[:]  # copying the values
    ret = {}
    interfaces = {}

    for libdir in (libdirs + bindirs):
        lib = ""
        if not os.path.exists(libdir):
            # Conan 2
            # conanfile.output.debug("The library folder doesn't exist: {}".format(libdir))
            continue
        files = os.listdir(libdir)
        lib_path = None
        for f in files:
            full_path = os.path.join(libdir, f)
            if not os.path.isfile(full_path):  # Make sure that directories are excluded
                continue
            # Users may not name their libraries in a conventional way. For example, directly
            # use the basename of the lib file as lib name.
            if f in libs:
                lib = f
                libs.remove(f)
                lib_path = full_path
                break
            name, ext = os.path.splitext(f)
            if name not in libs and name.startswith("lib"):
                name = name[3:]
            if name in libs:
                # FIXME: Should it read a conf variable to know unexpected extensions?
                if (is_shared and ext in (".so", ".dylib", ".lib", ".dll")) or \
                   (not is_shared and ext in (".a", ".lib")):
                    lib = name
                    libs.remove(name)
                    lib_path = full_path
                    break
        if lib_path is not None:
            _, ext = os.path.splitext(lib_path)
            if is_shared and ext == ".lib":  # Windows interface library
                interfaces[lib] = _relativize_path(lib_path, relative_to_path=relative_to_path)
            else:
                ret[lib] = _relativize_path(lib_path, relative_to_path=relative_to_path)

    libraries = []
    for lib, lib_path in ret.items():
        interface_library = None
        if lib_path.endswith(".dll"):
            if lib not in interfaces:
                raise ConanException(f"Windows needs a .lib for link-time and .dll for runtime."
                                     f"Only found {lib_path}")
            interface_library = interfaces.pop(lib)
        libraries.append(_LibInfo(lib, is_shared, lib_path, interface_library))
    # TODO: Would we want to manage the cases where DLLs are provided by the system?
    # Conan 2
    # conanfile.output.warning(f"The library/ies {libs} cannot be found in the dependency")
    return libraries


def _get_headers(cpp_info, package_folder_path):
    return ', '.join('"{}/**"'.format(_relativize_path(path, package_folder_path))
                     for path in cpp_info.includedirs)


def _get_includes(cpp_info, package_folder_path):
    return ', '.join('"{}"'.format(_relativize_path(path, package_folder_path))
                     for path in cpp_info.includedirs)


def _get_defines(cpp_info):
    return ', '.join('"{}"'.format(define.replace('"', '\\' * 3 + '"'))
                     for define in cpp_info.defines)


def _get_linkopts(cpp_info, os_build):
    link_opt = '"/DEFAULTLIB:{}"' if os_build == "Windows" else '"-l{}"'
    system_libs = [link_opt.format(lib) for lib in cpp_info.system_libs]
    shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags
    return ", ".join(system_libs + shared_flags)


def _get_copts(cpp_info):
    # FIXME: long discussions between copts (-Iflag) vs includes in Bazel. Not sure yet
    # includedirsflags = ['"-I{}"'.format(_relativize_path(d, package_folder_path))
    #                     for d in cpp_info.includedirs]
    cxxflags = [var.replace('"', '\\"') for var in cpp_info.cxxflags]
    cflags = [var.replace('"', '\\"') for var in cpp_info.cflags]
    return ", ".join(cxxflags + cflags)


# FIXME: Very fragile. Need UTs, and, maybe, move it to conan.tools.files
def _relativize_path(path, relative_to_path):
    """
    Relativize the path with regard to a given base path

    :param path: path to relativize
    :param relative_to_path: base path to prune from the path
    :return: Unix-like path relative to ``relative_to_path``. Otherwise, it returns
             the Unix-like ``path``.
    """
    if not path or not relative_to_path:
        return path
    p = path.replace("\\", "/")
    rel = relative_to_path.replace("\\", "/")
    if p.startswith(rel):
        return p[len(rel):].lstrip("/")
    elif rel in p:
        return p.split(rel)[-1].lstrip("/")
    else:
        return p.lstrip("/")


class _BazelDependenciesBZLGenerator:
    """
    Bazel needs to know all the dependencies for its current project. So, the only way
    to do that is to tell the WORKSPACE file how to load all the Conan ones. This is the goal
    of the function created by this class, the ``load_conan_dependencies`` one.

    More information:
        * https://bazel.build/reference/be/workspace#new_local_repository
    """

    filename = "dependencies.bzl"
    template = textwrap.dedent("""\
        # This Bazel module should be loaded by your WORKSPACE file.
        # Add these lines to your WORKSPACE one (assuming that you're using the "bazel_layout"):
        # load("@//bazel-conan-tools:dependencies.bzl", "load_conan_dependencies")
        # load_conan_dependencies()

        {% macro new_local_repository(pkg_name, pkg_folder, pkg_build_file_path) %}
            native.new_local_repository(
                name="{{pkg_name}}",
                path="{{pkg_folder}}",
                build_file="{{pkg_build_file_path}}",
            )
        {% endmacro %}
        def load_conan_dependencies():
        {% for pkg_name, pkg_folder, pkg_build_file_path in dependencies %}
        {{ new_local_repository(pkg_name, pkg_folder, pkg_build_file_path) }}
        {% endfor %}
        """)

    def __init__(self, conanfile, dependencies):
        self._conanfile = conanfile
        self._dependencies = dependencies

    def generate(self):
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        content = template.render(dependencies=self._dependencies)
        # Saving the BUILD (empty) and dependencies.bzl files
        save(self.filename, content)
        save("BUILD.bazel", "# This is an empty BUILD file to be able to load the "
                            "dependencies.bzl one.")


class _BazelBUILDGenerator:
    """
    This class creates the BUILD.bazel for each dependency where it's declared all the
    necessary information to load the libraries
    """

    # If both files exist, BUILD.bazel takes precedence over BUILD
    # https://bazel.build/concepts/build-files
    filename = "BUILD.bazel"
    template = textwrap.dedent("""\
    {% macro cc_import_macro(libs) %}
    {% for lib_info in libs %}
    cc_import(
        name = "{{ lib_info.name }}_precompiled",
        {% if lib_info.is_shared %}
        shared_library = "{{ lib_info.lib_path }}",
        {% else %}
        static_library = "{{ lib_info.lib_path }}",
        {% endif %}
        {% if lib_info.interface_path %}
        interface_library = "{{ lib_info.interface_path }}",
        {% endif %}
    )
    {% endfor %}
    {% endmacro %}
    {% macro cc_library_macro(obj) %}
    cc_library(
        name = "{{ obj["name"] }}",
        {% if obj["headers"] %}
        hdrs = glob([
            {{ obj["headers"] }}
        ]),
        {% endif %}
        {% if obj["includes"] %}
        includes = [
            {{ obj["includes"] }}
        ],
        {% endif %}
        {% if obj["defines"] %}
        defines = [
            {{ obj["defines"] }}
        ],
        {% endif %}
        {% if obj["linkopts"] %}
        linkopts = [
            {{ obj["linkopts"] }}
        ],
        {% endif %}
        {% if obj["copts"] %}
        copts = [
            {{ obj["copts"] }}
        ],
        {% endif %}
        visibility = ["//visibility:public"],
        {% if obj["libs"] or obj["dependencies"] %}
        deps = [
            {% for lib in obj["libs"] %}
            ":{{ lib.name }}_precompiled",
            {% endfor %}
            {% for name in obj["component_names"] %}
            ":{{ name }}",
            {% endfor %}
            {% for dep in obj["dependencies"] %}
            "{{ dep }}",
            {% endfor %}
        ],
        {% endif %}
    )
    {% endmacro %}
    load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

    # Components precompiled libs
    {% for component in components %}
    {{ cc_import_macro(component["libs"]) }}
    {% endfor %}
    # Root package precompiled libs
    {{ cc_import_macro(root["libs"]) }}
    # Components libraries declaration
    {% for component in components %}
    {{ cc_library_macro(component) }}
    {% endfor %}
    # Package library declaration
    {{ cc_library_macro(root) }}
    """)

    def __init__(self, conanfile, dep, root_package_info, components_info):
        self._conanfile = conanfile
        self._dep = dep
        self._root_package_info = root_package_info
        self._components_info = components_info

    @property
    def _is_shared_dependency(self):
        """
        Checking traits and shared option
        """
        default_value = self._dep.options.get_safe("shared") if self._dep.options else False
        # Conan 2.x
        # return {"shared-library": True,
        #         "static-library": False}.get(str(self._dep.package_type), default_value)
        return default_value

    @property
    def build_file_pah(self):
        """
        Returns the absolute path to the BUILD file created by Conan
        """
        return os.path.join(self._root_package_info.name, self.filename)

    @property
    def absolute_build_file_pah(self):
        """
        Returns the absolute path to the BUILD file created by Conan
        """
        return os.path.join(self._conanfile.generators_folder, self.build_file_pah)

    @property
    def package_folder(self):
        """
        Returns the package folder path
        """
        # If editable, package_folder can be None
        root_folder = self._dep.recipe_folder if self._dep.package_folder is None \
            else self._dep.package_folder
        return root_folder.replace("\\", "/")

    @property
    def package_name(self):
        """
        Wrapper to get the final name used for the root dependency cc_library declaration
        """
        return self._root_package_info.name

    def _get_context(self):
        def fill_info(info):
            ret = {
                "name": info.name,  # package name and components name
                "libs": {},
                "headers": "",
                "includes": "",
                "defines": "",
                "linkopts": "",
                "copts": "",
                "dependencies": info.requires,
                "component_names": []  # filled only by the root
            }
            if info.cpp_info is not None:
                cpp_info = info.cpp_info
                headers = _get_headers(cpp_info, package_folder_path)
                includes = _get_includes(cpp_info, package_folder_path)
                copts = _get_copts(cpp_info)
                defines = _get_defines(cpp_info)
                # Conan 2
                # linkopts = _get_linkopts(cpp_info, self._dep.settings_build.get_safe("os"))
                linkopts = _get_linkopts(cpp_info, self._dep.settings.get_safe("os"))
                libs = _get_libs(self._conanfile, cpp_info, is_shared=is_shared,
                                 relative_to_path=package_folder_path)
                ret.update({
                    "libs": libs,
                    "headers": headers,
                    "includes": includes,
                    "defines": defines,
                    "linkopts": linkopts,
                    "copts": copts
                })
            return ret

        is_shared = self._is_shared_dependency
        package_folder_path = self.package_folder
        context = dict()
        context["root"] = fill_info(self._root_package_info)
        context["components"] = []
        for component in self._components_info:
            component_context = fill_info(component)
            context["components"].append(component_context)
            context["root"]["component_names"].append(component_context["name"])
        return context

    def generate(self):
        context = self._get_context()
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        content = template.render(context)
        save(self.build_file_pah, content)


class _InfoGenerator:

    def __init__(self, conanfile, dep, build_context_activated=None):
        self._conanfile = conanfile
        self._dep = dep
        # Conan 2.x
        # self._transitive_reqs = get_transitive_requires(self._conanfile, dep)
        self._transitive_reqs = self._dep.dependencies.direct_host
        self._build_context_activated = build_context_activated or []

    def _get_cpp_info_requires_names(self, cpp_info):
        """
        Get all the valid names from the requirements ones given a CppInfo object.

        For instance, those requirements could be coming from:

        ```python
        from conan import ConanFile
        class PkgConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.requires = ["other::cmp1"]

            # Or:

            def package_info(self):
                self.cpp_info.components["cmp"].requires = ["other::cmp1"]
        ```
        """
        dep_ref_name = _get_package_reference_name(self._dep)
        ret = []
        for req in cpp_info.requires:
            pkg_ref_name, comp_ref_name = req.split("::") if "::" in req else (dep_ref_name, req)
            prefix = ":"  # Requirements declared in the same BUILD file
            # For instance, dep == "hello/1.0" and req == "other::cmp1" -> hello != other
            if dep_ref_name != pkg_ref_name:
                try:
                    req_conanfile = self._transitive_reqs[pkg_ref_name]
                    # Requirements declared in another dependency BUILD file
                    prefix = f"@{_get_package_name(req_conanfile)}//:"
                except KeyError:
                    continue  # If the dependency is not in the transitive, might be skipped
            else:  # For instance, dep == "hello/1.0" and req == "hello::cmp1" -> hello == hello
                req_conanfile = self._dep
            comp_name = _get_component_name(req_conanfile, comp_ref_name)
            ret.append(f"{prefix}{comp_name}")
        return ret

    @property
    def components_info(self):
        """
        Get the whole package and its components information like their own requires, names and even
        the cpp_info for each component.

        :return: `list` of `_PCInfo` objects with all the components information
        """
        if not self._dep.cpp_info.has_components:
            return []
        components_info = []
        # Loop through all the package's components
        for comp_ref_name, cpp_info in self._dep.cpp_info.get_sorted_components().items():
            # At first, let's check if we have defined some components requires, e.g., "dep::cmp1"
            comp_requires_names = self._get_cpp_info_requires_names(cpp_info)
            comp_name = _get_component_name(self._dep, comp_ref_name)
            # Save each component information
            components_info.append(_DepInfo(comp_name, comp_requires_names, cpp_info))
        return components_info

    @property
    def root_package_info(self):
        """
        Get the whole package information

        :return: `_PCInfo` object with the package information
        """
        pkg_name = _get_package_name(self._dep)
        # At first, let's check if we have defined some global requires, e.g., "other::cmp1"
        requires = self._get_cpp_info_requires_names(self._dep.cpp_info)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct dependencies,
            # e.g., requires = "other_pkg/1.0"
            for req in self._transitive_reqs.values():
                req_name = _get_package_name(req)
                requires.append(f"@{req_name}//:{req_name}")
        cpp_info = self._dep.cpp_info
        return _DepInfo(pkg_name, requires, cpp_info)


class BazelDeps:

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Activate the build context for the specified libraries
        self.build_context_activated = []

    def generate(self):
        """
        Save all the targets BUILD files and the dependencies.bzl one.

        Important! The dependencies.bzl file should be loaded by the WORKSPACE Bazel file.
        """
        # Conan 2
        # check_duplicated_generator(self, self._conanfile)
        requirements = get_requirements(self._conanfile, self.build_context_activated)
        deps_info = []
        for require, dep in requirements:
            # Bazel info generator
            info_generator = _InfoGenerator(self._conanfile, dep)
            root_package_info = info_generator.root_package_info
            components_info = info_generator.components_info
            # Generating single BUILD files per dependency
            bazel_generator = _BazelBUILDGenerator(self._conanfile, dep,
                                                   root_package_info, components_info)
            bazel_generator.generate()
            # Saving pieces of information from each BUILD file
            deps_info.append((
                bazel_generator.package_name,  # package name
                bazel_generator.package_folder,  # path to dependency folder
                bazel_generator.absolute_build_file_pah  # path to the BUILD file created
            ))
        # dependencies.bzl has all the information about where to look for the dependencies
        bazel_dependencies_module_generator = _BazelDependenciesBZLGenerator(self._conanfile,
                                                                             deps_info)
        bazel_dependencies_module_generator.generate()
