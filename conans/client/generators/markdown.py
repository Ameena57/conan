import os
import textwrap

from jinja2 import DictLoader
from jinja2 import Environment
from conans.model import Generator
import datetime


render_cpp_info = textwrap.dedent("""
    {% macro join_list_sources(items) -%}
    ``{{ "``, ``".join(items) }}``
    {%- endmacro %}

    {% macro render_cpp_info(cpp_info) -%}
    {%- if cpp_info.requires is iterable and cpp_info.requires %}
    * Requires: {{ join_list_sources(cpp_info.requires) }}
    {%- endif %}
    {%- if cpp_info.libs %}
    * Libraries: {{ join_list_sources(cpp_info.libs) }}
    {%- endif %}
    {%- if cpp_info.system_libs %}
    * Systems libs: {{ join_list_sources(cpp_info.system_libs) }}
    {%- endif %}
    {%- if cpp_info.defines %}
    * Preprocessor definitions: {{ join_list_sources(cpp_info.defines) }}
    {%- endif %}
    {%- if cpp_info.cflags %}
    * C_FLAGS: {{ join_list_sources(cpp_info.cflags) }}
    {%- endif %}
    {%- if cpp_info.cxxflags %}
    * CXX_FLAGS: {{ join_list_sources(cpp_info.cxxflags) }}
    {%- endif %}
    {%- endmacro %}
""")

buildsystem_cmake_tpl = textwrap.dedent("""
    {% set cmake_find_package_name = cpp_info.get_name("cmake_find_package") %}
    {% set cmake_find_package_filename = cpp_info.get_filename("cmake_find_package") %}

    ### CMake

    #### Generator [CMakeToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake/cmaketoolchain.html)
    `CMakeToolchain` is the toolchain generator for CMake. It will generate a toolchain
    file that can be used in the command-line invocation of CMake with
    `-DCMAKE_TOOLCHAIN_FILE=conantoolchain.cmake`. This generator translates the current
    package configuration, settings, and options, into CMake toolchain syntax.

    #### Generator [CMakeDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake/cmakedeps.html)
    The `CMakeDeps` helper will generate one `xxxx-config.cmake` file per dependency,
    together with other necessary `.cmake` files like version, flags, and directory data
    or configuration.

    Add these lines to your `CMakeLists.txt`:

    ```
    find_package({{ cmake_find_package_filename }})

    # Use the global target
    target_link_libraries(<library_name> {{ cmake_find_package_name }}::{{ cmake_find_package_name }})

    {% if cpp_info.components %}
    # Or link just one of its components
    {% for cmp_name, cmp_cpp_info in cpp_info.components.items() -%}
    target_link_libraries(<library_name> {{ cmake_find_package_name }}::{{ cmp_cpp_info.get_name("cmake_find_package") }})
    {% endfor %}
    {%- endif %}
    ```

    {% set cmake_build_modules = cpp_info.build_modules.get('cmake', None) %}
    {% set cmake_find_package_build_modules = cpp_info.build_modules.get('cmake_find_package', None) %}
    {% if cmake_build_modules or cmake_find_package_build_modules %}
    This generator will include some _build modules_:
    {%- endif %}
    {% if cmake_build_modules %}
    {% for bm in cmake_build_modules -%}
    * `{{ bm }}`
      ```
      {{ '/'.join([cpp_info.rootpath, bm])|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
    {% if cmake_find_package_build_modules %}
    {% for bm in cmake_find_package_build_modules -%}
    * `{{ bm }}`
      ```
      {{ '/'.join([cpp_info.rootpath, bm])|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
""")

buildsystem_vs_tpl = textwrap.dedent("""
    ### Visual Studio

    #### Generator [MSBuildToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html#msbuildtoolchain)
    `MSBuildToolchain` is the toolchain generator for MSBuild. It will generate MSBuild
    properties files that can be added to the Visual Studio solution projects. This generator
    translates the current package configuration, settings, and options, into MSBuild
    properties files syntax.

    #### Generator [MSBuildDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html#msbuilddeps)
    `MSBuildDeps` is the dependency information generator for Microsoft MSBuild build
    system. It will generate multiple `xxxx.props` properties files, one per dependency of
    a package, to be used by consumers using MSBuild or Visual Studio, just adding the
    generated properties files to the solution and projects.
""")

buildsystem_autotools_tpl = textwrap.dedent("""
    ### Autotools

    #### Generator [AutotoolsToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu/autotoolstoolchain.html)
    `AutotoolsToolchain` is the toolchain generator for Autotools. It will generate
    shell scripts containing environment variable definitions that the autotools build
    system can understand.

    `AutotoolsToolchain` will generate the `conanautotoolstoolchain.sh` or
    `conanautotoolstoolchain.bat` files after a `conan install` command:

    ```
    $ conan install conanfile.py # default is Release
    $ source conanautotoolstoolchain.sh
    # or in Windows
    $ conanautotoolstoolchain.bat
    ```

    If your autotools scripts expect to find dependencies using pkg_config, use the
    `PkgConfigDeps` generator. Otherwise, use `AutotoolsDeps`.

    #### Generator AutotoolsDeps
    The AutotoolsDeps is the dependencies generator for Autotools. It will generate
    shell scripts containing environment variable definitions that the autotools
    build system can understand.

    The AutotoolsDeps will generate after a conan install command the
    conanautotoolsdeps.sh or conanautotoolsdeps.bat files:

    ```
    $ conan install conanfile.py # default is Release
    $ source conanautotoolsdeps.sh
    # or in Windows
    $ conanautotoolsdeps.bat
    ```


    #### Generator PkgConfigDeps
    This package provides one *pkg-config* file ``{{ cpp_info.get_filename('pkg_config') }}.pc`` with
    all the information from the library
    {% if cpp_info.components -%}
    and another file for each of its components:
    {%- for cmp_name, cmp_cpp_info in cpp_info.components.items() -%}
    ``{{ cmp_cpp_info.get_filename('pkg_config') }}.pc``{% if not loop.last %},{% endif %}
    {%- endfor -%}
    {%- endif -%}.
    Use your *pkg-config* tool as usual to consume the information provided by the Conan package.

    {% set build_modules = cpp_info.build_modules.get('pkg_config', None) %}
    {% if build_modules %}
    This generator will include some _build modules_:
    {% for bm in build_modules -%}
    * `{{ bm }}`
      ```
      {{ '/'.join([cpp_info.rootpath, bm])|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
""")

buildsystem_other_tpl = textwrap.dedent("""
    ### Other build systems
    Conan includes generators for [several more build systems](https://docs.conan.io/en/latest/integrations/build_system.html),
    and you can even write [custom integrations](https://docs.conan.io/en/latest/integrations/custom.html)
    if needed.
""")

requirement_tpl = textwrap.dedent("""
    {% from 'render_cpp_info' import render_cpp_info %}

    # {{ cpp_info.name }}/{{ cpp_info.version }}

    ---

    ## How to use this recipe

    You can use this recipe with different build systems. For each build system, Conan
    provides different generators that you must list in the generators property of the
    `conanfile.py`. Alternatively, you can use the command line argument  `--generator/-g`
    in the `conan install` command.

    [Here](https://docs.conan.io/en/latest/integrations.html) you can read more about Conan
    integration with several build systems, compilers, IDEs, etc.


    {% if requires or required_by %}
    ## Dependencies
    {% if requires %}
    * ``{{ cpp_info.name }}`` requires:
        {% for dep_name, dep_cpp_info in requires -%}
        [{{ dep_name }}/{{ dep_cpp_info.version }}]({{ dep_name }}){% if not loop.last %}, {% endif %}
        {%- endfor -%}
    {%- endif %}
    {%- if required_by %}
    * ``{{ cpp_info.name }}`` is required by:
        {%- for dep_name, dep_cpp_info in required_by %}
        [{{ dep_name }}/{{ dep_cpp_info.version }}]({{ dep_name }}){% if not loop.last %}, {% endif %}
        {%- endfor %}
    {%- endif %}
    {% endif %}

    ## Build Systems

    {% include 'buildsystem_cmake' %}
    {% include 'buildsystem_vs' %}
    {% include 'buildsystem_autotools' %}
    {% include 'buildsystem_other' %}

    ## Information for consumers

    {% if cpp_info.components %}
    {% for cmp_name, cmp_cpp_info in cpp_info.components.items() %}
    * Component ``{{ cpp_info.name }}::{{ cmp_name }}``:
    {{ render_cpp_info(cmp_cpp_info)|indent(width=2) }}
    {%- endfor %}
    {% else %}
    {{ render_cpp_info(cpp_info)|indent(width=0) }}
    {% endif %}

    ## Header files

    List of header files exposed by this package. Use them in your ``#include`` directives:

    ```cpp
    {%- for header in headers %}
    {{ header }}
    {%- endfor %}
    ```

    ---
    ---
    Conan **{{ conan_version }}**. JFrog LTD. [https://conan.io](https://conan.io). Autogenerated {{ now.strftime('%Y-%m-%d %H:%M:%S') }}.
""")


class MarkdownGenerator(Generator):

    def _list_headers(self, cpp_info):
        rootpath = cpp_info.rootpath
        for include_dir in cpp_info.includedirs:
            for root, _, files in os.walk(os.path.join(cpp_info.rootpath, include_dir)):
                for f in files:
                    yield os.path.relpath(os.path.join(root, f), os.path.join(rootpath, include_dir))

    def _list_requires(self, cpp_info):
        return [(it, self.conanfile.deps_cpp_info[it]) for it in cpp_info.public_deps]

    def _list_required_by(self, cpp_info):
        for other_name, other_cpp_info in self.conanfile.deps_cpp_info.dependencies:
            if cpp_info.name in other_cpp_info.public_deps:
                yield other_name, other_cpp_info

    @property
    def filename(self):
        pass

    @property
    def content(self):
        dict_loader = DictLoader({
            'render_cpp_info': render_cpp_info,
            'package.md': requirement_tpl,
            'buildsystem_cmake': buildsystem_cmake_tpl,
            'buildsystem_vs': buildsystem_vs_tpl,
            'buildsystem_autotools': buildsystem_autotools_tpl,
            'buildsystem_other': buildsystem_other_tpl
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
        for name, cpp_info in self.conanfile.deps_cpp_info.dependencies:
            ret["{}.md".format(name)] = template.render(
                cpp_info=cpp_info,
                headers=self._list_headers(cpp_info),
                requires=list(self._list_requires(cpp_info)),
                required_by=list(self._list_required_by(cpp_info)),
                conan_version=conan_version,
                now=datetime.datetime.now()
            )
        return ret
