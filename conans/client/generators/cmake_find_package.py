import textwrap

from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package_common import target_template, \
    CMakeFindPackageCommonMacros, find_transitive_dependencies, target_component_template
from conans.client.generators.cmake_multi import extend
from conans.errors import ConanException
from conans.model import Generator


class CMakeFindPackageGenerator(Generator):
    template = textwrap.dedent("""
        {macros_and_functions}

        include(FindPackageHandleStandardArgs)

        conan_message(STATUS "Conan: Using autogenerated Find{name}.cmake")
        # Global approach
        set({name}_FOUND 1)
        set({name}_VERSION "{version}")

        find_package_handle_standard_args({name} REQUIRED_VARS {name}_VERSION VERSION_VAR {name}_VERSION)
        mark_as_advanced({name}_FOUND {name}_VERSION)

        {find_libraries_block}
        {target_approach_block}
        """)
    target_approach_template = textwrap.dedent("""
        if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
            # Target approach
            if(NOT TARGET {global_name}::{name})
                add_library({global_name}::{name} INTERFACE IMPORTED)
                if({name}_INCLUDE_DIRS)
                  set_target_properties({global_name}::{name} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${{{name}_INCLUDE_DIRS}}")
                endif()
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_LINK_LIBRARIES "${{{name}_LIBRARIES_TARGETS}};${{{name}_LINKER_FLAGS_LIST}}")
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{{name}_COMPILE_DEFINITIONS}})
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_COMPILE_OPTIONS "${{{name}_COMPILE_OPTIONS_LIST}}")
                {find_dependencies_block}
            endif()
        endif()
        """)
    component_template = textwrap.dedent("""
        if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
            # Target approach
            if(NOT TARGET {global_name}::{name})
                add_library({global_name}::{name} INTERFACE IMPORTED)
                set_target_properties({global_name}::{name} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${{{name}_INCLUDE_DIRS}}")
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_LINK_DIRECTORIES "${{{name}_LIB_DIRS}}")
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_LINK_LIBRARIES "${{{name}_LIBS}};${{{name}_LINKER_FLAGS_LIST}}")
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{{name}_COMPILE_DEFINITIONS}})
                set_property(TARGET {global_name}::{name} PROPERTY INTERFACE_COMPILE_OPTIONS "${{{name}_COMPILE_OPTIONS_LIST}}")
            endif()
        endif()
        """)

    @property
    def filename(self):
        return None

    @property
    def content(self):
        ret = {}
        for dep_name, cpp_info in self.deps_build_info.dependencies:
            find_dep_name = cpp_info.get_name("cmake_find_package")
            ret["Find%s.cmake" % find_dep_name] = self._find_for_dep(dep_name, cpp_info)
        return ret

    def _find_for_dep(self, dep_name, cpp_info):
        dep_findname = cpp_info.get_name("cmake_find_package")
        # The common macros
        macros_and_functions = "\n".join([
            CMakeFindPackageCommonMacros.conan_message,
            CMakeFindPackageCommonMacros.apple_frameworks_macro,
            CMakeFindPackageCommonMacros.conan_package_library_targets,
            CMakeFindPackageCommonMacros.conan_package_components_targets
        ])

        # compose the cpp_info with its "debug" or "release" specific config
        dep_cpp_info = cpp_info
        build_type = self.conanfile.settings.get_safe("build_type")
        if build_type:
            dep_cpp_info = extend(dep_cpp_info, build_type.lower())

        deps = DepsCppCmake(dep_cpp_info)
        public_deps_findnames = [self.deps_build_info[dep].get_name("cmake_find_package") for dep in
                                 dep_cpp_info.public_deps]
        find_dependencies_block = ""
        if dep_cpp_info.public_deps:
            # Here we are generating FindXXX, so find_modules=True
            f = find_transitive_dependencies(public_deps_findnames, find_modules=True)
            # proper indentation
            find_dependencies_block = "".join("        " + line if line.strip() else line
                                              for line in f.splitlines(True))

        find_libraries_block = ""
        target_approach_block = ""
        for comp_name, comp in cpp_info.components.items():
            comp_findname = comp.get_name("cmake_find_package")
            deps_component = DepsCppCmake(comp)
            comp_requires_findnames = []
            for require in comp.requires:
                if "::" in require:
                    comp_require_dep_name = require[:require.find("::")]
                    if comp_require_dep_name not in self.deps_build_info.deps:
                        raise ConanException("Component '%s' not found: '%s' is not a package "
                                             "requirement" % (require, comp_require_dep_name))
                    comp_require_dep_findname = self.deps_build_info[comp_require_dep_name].get_name("cmake_find_package")
                    comp_require_comp_name = require[require.find("::")+2:]
                    if comp_require_comp_name in self.deps_build_info.deps:
                        comp_require_comp_findname = comp_require_dep_findname
                    elif comp_require_comp_name in self.deps_build_info[comp_require_dep_name].components:
                        comp_require_comp_findname = self.deps_build_info[comp_require_dep_name].components[comp_require_comp_name].get_name("cmake_find_package")
                    else:
                        raise ConanException("Component '%s' not found in '%s' package requirement"
                                             % (require, comp_require_dep_name))
                    comp_requires_findnames.append("{}::{}".format(comp_require_dep_findname, comp_require_comp_findname))
                else:
                    comp_require_findname = self.deps_build_info[dep_name].components[require].get_name("cmake_find_package")
                    comp_requires_findnames.append("{}::{}".format(dep_findname, comp_require_findname))
            comp_requires_findnames = ";".join(comp_requires_findnames)
            find_libraries_block += target_component_template.format(name=comp_findname,
                                                                     global_name=dep_findname,
                                                                     deps=deps_component,
                                                                     build_type_suffix="",
                                                                     deps_names=comp_requires_findnames)
            target_approach_block += self.component_template.format(global_name=dep_findname,
                                                                    name=comp_findname)

        public_deps_findnames = ";".join(["{n}::{n}".format(n=n) for n in public_deps_findnames])
        find_libraries_block += target_template.format(name=dep_findname, deps=deps,
                                                       build_type_suffix="",
                                                       deps_names=public_deps_findnames)
        target_approach_block += self.target_approach_template.format(global_name=dep_findname,
                                                                      name=dep_findname,
                                                                      find_dependencies_block=find_dependencies_block)

        tmp = self.template.format(macros_and_functions=macros_and_functions,
                                   name=dep_findname,
                                   version=dep_cpp_info.version,
                                   find_libraries_block=find_libraries_block,
                                   target_approach_block=target_approach_block)
        return tmp
