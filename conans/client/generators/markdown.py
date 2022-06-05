import datetime
import os
import textwrap

from jinja2 import DictLoader
from jinja2 import Environment

from conan.tools.cmake.cmakedeps.cmakedeps import CMakeDeps
from conan.tools.cmake.cmakedeps.templates import (
    CMakeDepsFileTemplate,
    get_cmake_package_name as cmake_get_file_name)
from conan.tools.gnu.pkgconfigdeps.pc_info_loader import (
    _get_component_name as pkgconfig_get_component_name,
    _get_name_with_namespace as pkgconfig_get_name_with_namespace,
    _get_package_name as pkgconfig_get_package_name
)
from conans.model import Generator


requirement_tpl = textwrap.dedent("""
    {% from 'macros' import render_component_cpp_info %}

    # {{ requirement }}

    ---

    {% if requires %}

    <br>

    ## {{ requirement }} dependencies
    {% for dep_name, dep in requires %}
    * [{{ dep }}](https://conan.io/center/{{ dep_name }})
    {%- endfor -%}
    {%- endif %}

    <br>

    ## Using the {{ requirement.ref.name }} Conan Package

    <br>

    Conan integrates with different build systems. You can declare which build system you want your project to use setting in the **[generators]** section of the [conanfile.txt](https://docs.conan.io/en/latest/reference/conanfile_txt.html#generators) or using the **generators** attribute in the [conanfile.py](https://docs.conan.io/en/latest/reference/conanfile/attributes.html#generators). Here, there is some basic information you can use to integrate **{{ requirement.ref.name }}** in your own project. For more detailed information, please [check the Conan documentation](https://docs.conan.io/en/latest/getting_started.html).

    {% include 'buildsystem_cmake' %}
    {% include 'buildsystem_vs' %}
    {% include 'buildsystem_autotools' %}
    {% include 'buildsystem_other' %}
    {% include 'components' %}
    {% include 'headers' %}

    ---
    ---
    Conan **{{ conan_version }}**. JFrog LTD. [https://conan.io](https://conan.io). Autogenerated {{ now.strftime('%Y-%m-%d %H:%M:%S') }}.
""")

macros = textwrap.dedent("""
    {% macro join_list_code(items) -%}
    ``{{ "``, ``".join(items) }}``
    {%- endmacro %}

    {% macro join_list_bold(items) -%}
    **{{ "**, **".join(items) }}**
    {%- endmacro %}

    {% macro render_component_cpp_info(target_name, pc_name, cpp_info) %}
    * CMake target name: ``{{ target_name }}``
    * pkg-config *.pc* file: **{{ pc_name }}.pc**
    {%- if cpp_info.requires is iterable and cpp_info.requires %}
    * Requires other components: {{ join_list_bold(cpp_info.requires) }}
    {%- endif %}
    {%- if cpp_info.libs %}
    * Links to libraries: {{ join_list_bold(cpp_info.libs) }}
    {%- endif %}
    {%- if cpp_info.system_libs %}
    * Systems libs: {{ join_list_bold(cpp_info.system_libs) }}
    {%- endif %}
    {%- if cpp_info.defines %}
    * Preprocessor definitions: {{ join_list_code(cpp_info.defines) }}
    {%- endif %}
    {%- if cpp_info.cflags %}
    * C_FLAGS: {{ join_list_code(cpp_info.cflags) }}
    {%- endif %}
    {%- if cpp_info.cxxflags %}
    * CXX_FLAGS: {{ join_list_code(cpp_info.cxxflags) }}
    {%- endif %}
    {%- endmacro %}
""")

buildsystem_cmake_tpl = textwrap.dedent("""

    <br>

    ## Using {{ requirement.ref.name }} with CMake

    <br>

    ### [Conan CMake generators](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake.html)

    <br>

    * [CMakeDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake/cmakedeps.html): generates information about where the **{{ requirement.ref.name }}** library and its dependencies {% if requires %} ({% for dep_name, dep in requires %} [{{ dep_name }}](https://conan.io/center/{{ dep_name }}){% if not loop.last %}, {% endif %} {%- endfor -%}) {%- endif %} are installed together with other information like version, flags, and directory data or configuration. CMake will use this files when you invoke ``find_package()`` in your *CMakeLists.txt*.

    * [CMakeToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake/cmaketoolchain.html): generates a CMake toolchain file that you can later invoke with CMake in the command line using `-DCMAKE_TOOLCHAIN_FILE=conantoolchain.cmake`.

    Declare these generators in your **conanfile.txt** along with your **{{ requirement.ref.name }}** dependency like:

    ```ini
    [requires]
    {{ requirement }}

    [generators]
    CMakeDeps
    CMakeToolchain
    ```

    <br>

    To use **{{ requirement.ref.name }}** in a simple CMake project with this structure:

    ```shell
    .
    |-- CMakeLists.txt
    |-- conanfile.txt
    `-- src
        `-- main.{{ project_extension }}
    ```

    <br>

    Your **CMakeLists.txt** could look similar to this, using the global **{{ cmake_variables.global_target_name }}** CMake's target:

    ```cmake
    cmake_minimum_required(VERSION 3.15)
    project({{ requirement.ref.name }}_project {{ project_type }})

    find_package({{ cmake_variables.file_name }})

    add_executable(${PROJECT_NAME} src/main{{ project_extension }})

    # Use the global target
    target_link_libraries(${PROJECT_NAME} {{ cmake_variables.global_target_name }})
    ```

    <br>

    To install **{{ requirement }}**, its dependencies and build your project, you just have to do:

    ```shell
    # for Linux/macOS
    $ conan install . --install-folder cmake-build-release --build=missing
    $ cmake . -DCMAKE_TOOLCHAIN_FILE=cmake-build-release/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release
    $ cmake --build .

    # for Windows and Visual Studio 2017
    $ conan install . --output-folder cmake-build --build=missing
    $ cmake . -G "Visual Studio 15 2017" -DCMAKE_TOOLCHAIN_FILE=cmake-build/conan_toolchain.cmake
    $ cmake --build . --config Release
    ```

    {% if requirement.cpp_info.has_components %}

    <br>

    {% for component_name, target_name in cmake_variables.component_alias.items() %}
    {%- if loop.index==1 %}

    As the {{ requirement.ref.name }} Conan package defines components, you can link only the desired parts of the library in your project. For example, linking only with the {{ requirement.ref.name }} **{{ component_name }}** component, through the **{{ target_name }}** target.

    ```cmake
    ...
    # Link just to {{ requirement.ref.name }} {{ component_name }} component
    target_link_libraries(${PROJECT_NAME} {{ target_name }})
    ```

    <br>

    To check all the available components for **{{ requirement.ref.name }}** Conan package, please check the dedicated section at the end of this document.

    {%- endif %}
    {%- endfor %}

    {%- endif %}

    {% set cmake_build_modules = requirement.cpp_info.get_property('cmake_build_modules') %}
    {% if cmake_build_modules %}

    <br>

    ### Declared CMake build modules

    <br>

    {% for bm in cmake_build_modules -%}
    #### {{ relpath(bm, package_folder) | replace("\\\\", "/") }}
      ```cmake
      {{ bm|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}

""")

buildsystem_vs_tpl = textwrap.dedent("""

    <br>

    ## Using {{ requirement.ref.name }} with Visual Studio

    <br>

    ### [Visual Studio Conan generators](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html)

    <br>

    * [MSBuildDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html#msbuilddeps): generates the **conandeps.props** properties file with information about where the **{{ requirement.ref.name }}** library and its dependencies {% if requires %} ({% for dep_name, dep in requires %} [{{ dep_name }}](https://conan.io/center/{{ dep_name }}){% if not loop.last %}, {% endif %} {%- endfor -%}) {%- endif %} are installed together with other information like version, flags, and directory data or configuration.

    * [MSBuildToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html#msbuildtoolchain): Generates the **conantoolchain.props** properties file with the current package configuration, settings, and options.

    Declare these generators in your **conanfile.txt** along with your **{{ requirement.ref.name }}** dependency like:

    ```ini
    [requires]
    {{ requirement }}

    [generators]
    MSBuildDeps
    MSBuildToolchain
    ```

    <br>

    Please, [check the Conan documentation](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html) for more detailed information on how to add these properties files to your Visual Studio projects.

""")

buildsystem_autotools_tpl = textwrap.dedent("""

    <br>

    ## Using {{ requirement.ref.name }} with Autotools and pkg-config

    <br>

    ### [Autotools Conan generators](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu.html)

    <br>

    * [AutotoolsToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu/autotoolstoolchain.html): generates the **conanautotoolstoolchain.sh/bat** script translating information from the current package configuration, settings, and options setting some enviroment variables for Autotools like: ``CPPFLAGS``, ``CXXFLAGS``, ``CFLAGS`` and ``LDFLAGS``. It will also generate a ``deactivate_conanautotoolstoolchain.sh/bat`` so you can restore your environment.

    * [AutotoolsDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu/autotoolsdeps.html): generates the **conanautotoolsdeps.sh/bat** script with information about where the **{{ requirement.ref.name }}** library and its dependencies {% if requires %} ({% for dep_name, dep in requires %} [{{ dep_name }}](https://conan.io/center/{{ dep_name }}){% if not loop.last %}, {% endif %} {%- endfor -%}) {%- endif %} are installed together with other information like version, flags, and directory data or configuration. This is done setting some enviroment variables for Autotools like: ``LIBS``, ``CPPFLAGS``,``CXXFLAGS``, ``CFLAGS`` and ``LDFLAGS``.  It will also generate a ``deactivate_conanautotoolsdeps.sh/bat`` so you can restore your environment.

    Declare these generators in your **conanfile.txt** along with your **{{ requirement.ref.name }}** dependency like:

    ```ini
    [requires]
    {{ requirement }}

    [generators]
    AutotoolsToolchain
    AutotoolsDeps
    ```

    <br>

    Then, building your project is as easy as:

    ```shell
    $ conan install .
    # set the environment variables for Autotools
    $ source conanautotoolstoolchain.sh
    $ source conanautotoolsdeps.sh
    $ ./configure
    $ make

    # restore the environment after the build is completed
    $ source deactivate_conanautotoolstoolchain.sh
    $ source deactivate_conanautotoolsdeps.sh
    ```

    <br>

    ### [pkg-config Conan generator](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu/pkgconfigdeps.html)

    <br>

    * [PkgConfigDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu/pkgconfigdeps.html): generates the **{{ pkgconfig_variables.pkg_name }}.pc** file (and the ones corresponding to **{{ requirement.ref.name }}** dependencies) with information about the dependencies that can be later used by the **pkg-config** tool pkg-config to collect data about the libraries Conan installed.

    <br>

    You can use this generator instead of the **AutotoolsDeps** one:

    ```ini
    [requires]
    {{ requirement }}

    [generators]
    AutotoolsToolchain
    PkgConfigDeps
    ```

    <br>

    And then using **pkg-config** to set the environment variables you want, like:

    ```shell
    $ conan install .
    # set the environment variables for Autotools
    $ source conanautotoolstoolchain.sh

    $ export CPPFLAGS="$CPPFLAGS $(pkg-config --cflags {{ requirement.ref.name }})"
    $ export LIBS="$LIBS $(pkg-config --libs-only-l {{ requirement.ref.name }})"
    $ export LDFLAGS="$LDFLAGS $(pkg-config --libs-only-L --libs-only-other {{ requirement.ref.name }})"

    $ ./configure
    $ make

    # restore the environment after the build is completed
    $ source deactivate_conanautotoolstoolchain.sh
    ```

    {% if requirement.cpp_info.has_components %}

    <br>

    As the {{ requirement.ref.name }} Conan package defines components you can use them to link only that desired part of the library in your project.  To check all the available components for **{{ requirement.ref.name }}** Conan package, and the corresponding *.pc* files names, please check the dedicated section at the end of this document.

    {%- endif %}
""")

buildsystem_other_tpl = textwrap.dedent("""

    <br>

    ## Other build systems

    <br>

    Please, [check the Conan documentation](https://docs.conan.io/en/latest/reference/conanfile/tools.html) for other integrations besides the ones listed in this document.

""")

components_tpl = textwrap.dedent("""

    {% if requirement.cpp_info.has_components %}

    <br>

    ## Declared components for {{ requirement.ref.name }}

    <br>

    These are all the declared components for the **{{ requirement.ref.name }}** Conan package:

    {%- for component_name, component_cpp_info in requirement.cpp_info.components.items() %}
    {%- if component_name %}
    * Component **{{ component_name }}**:
    {{- render_component_cpp_info(cmake_variables.component_alias[component_name], pkgconfig_variables.component_alias[component_name], component_cpp_info)|indent(width=2) }}
    {%- endif %}
    {%- endfor %}
    {%- endif %}
""")

headers_tpl = textwrap.dedent("""

    <br>

    ## Exposed header files for {{ requirement.ref.name }}

    <br>

    ```cpp
    {%- for header in headers %}
    #include <{{ header }}>
    {%- endfor %}
    ```

    <br>

""")


class MarkdownGenerator(Generator):
    @staticmethod
    def _list_headers(requirement):
        for include_dir in requirement.cpp_info.includedirs:
            for root, _, files in os.walk(os.path.join(requirement.package_folder, include_dir)):
                for f in files:
                    yield os.path.relpath(os.path.join(root, f), os.path.join(requirement.package_folder, include_dir))

    @staticmethod
    def _list_requires(requirement):
        return [(dep.ref.name, dep) for dep in requirement.dependencies.host.values()]

    @property
    def filename(self):
        pass

    @property
    def content(self):
        dict_loader = DictLoader({
            'macros': macros,
            'package.md': requirement_tpl,
            'buildsystem_cmake': buildsystem_cmake_tpl,
            'buildsystem_vs': buildsystem_vs_tpl,
            'buildsystem_autotools': buildsystem_autotools_tpl,
            'buildsystem_other': buildsystem_other_tpl,
            'components': components_tpl,
            'headers': headers_tpl
        })
        env = Environment(loader=dict_loader)
        template = env.get_template('package.md')

        def read_pkg_file(filename):
            try:
                return open(filename, 'r').read()
            except IOError:
                return '# Error reading file content. Please report.'

        env.filters['read_pkg_file'] = read_pkg_file

        from conans import __version__ as conan_version
        ret = {}
        for requirement in self.conanfile.dependencies.host.values():
            cmake_deps = CMakeDeps(self.conanfile)
            cmake_deps_template = CMakeDepsFileTemplate(cmake_deps,
                                                        requirement,
                                                        self.conanfile,
                                                        generating_module=False)

            cmake_component_alias = {
                component_name: cmake_deps_template.get_component_alias(requirement, component_name)
                for component_name, _
                in requirement.cpp_info.components.items()
                if component_name
            }

            project_type = 'C'
            project_extension = '.c'
            if requirement.settings.get_safe('compiler.libcxx') or requirement.settings.get_safe('compiler.cppstd'):
                project_type = 'CXX'
                project_extension = '.cpp'

            cmake_variables = {
                'global_target_name': requirement.cpp_info.get_property('cmake_target_name') or "{0}::{0}".format(requirement.ref.name),
                'component_alias': cmake_component_alias,
                'file_name': cmake_get_file_name(requirement)
            }

            pkgconfig_component_alias = {
                component_name: pkgconfig_get_component_name(requirement, component_name) or
                                pkgconfig_get_name_with_namespace(pkgconfig_get_package_name(requirement), component_name)
                for component_name, _
                in requirement.cpp_info.components.items()
                if component_name
            }
            pkgconfig_variables = {
                'pkg_name': pkgconfig_get_package_name(requirement),
                'component_alias': pkgconfig_component_alias
            }

            ret["{}.md".format(requirement.ref.name)] = template.render(
                requirement=requirement,
                headers=self._list_headers(requirement),
                requires=list(self._list_requires(requirement)),
                cmake_variables=cmake_variables,
                pkgconfig_variables=pkgconfig_variables,
                package_folder=requirement.package_folder,
                relpath=os.path.relpath,
                conan_version=conan_version,
                now=datetime.datetime.now(),
                project_type=project_type,
                project_extension=project_extension
            )

        return ret
