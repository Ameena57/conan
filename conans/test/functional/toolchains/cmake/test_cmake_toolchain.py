import os
import platform
import textwrap

import pytest

from conan.tools.cmake.presets import load_cmake_presets
from conan.tools.files.files import load_toolchain_args
from conans.model.ref import ConanFileReference
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import save


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.parametrize("compiler, version, update, runtime",
                         [("msvc", "192", None, "dynamic"),
                          ("msvc", "192", "6", "static"),
                          ("msvc", "192", "8", "static")])
def test_cmake_toolchain_win_toolset(compiler, version, update, runtime):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.update": update,
                "compiler.cppstd": "17",
                "compiler.runtime": runtime,
                "build_type": "Release",
                "arch": "x86_64"}

    # Build the profile according to the settings provided
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")

    client.save({"conanfile.py": conanfile})
    client.run("install . {}".format(settings))
    toolchain = client.load("conan_toolchain.cmake")
    if update is not None:  # Fullversion
        value = "version=14.{}{}".format(version[-1], update)
    else:
        value = "v14{}".format(version[-1])
    assert 'set(CMAKE_GENERATOR_TOOLSET "{}" CACHE STRING "" FORCE)'.format(value) in toolchain


def test_cmake_toolchain_user_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    save(client.cache.new_config_path, "tools.cmake.cmaketoolchain:user_toolchain+=mytoolchain.cmake")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'include("mytoolchain.cmake")' in toolchain


def test_cmake_toolchain_custom_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    save(client.cache.new_config_path, "tools.cmake.cmaketoolchain:toolchain_file=mytoolchain.cmake")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert not os.path.exists(os.path.join(client.current_folder, "conan_toolchain.cmake"))
    presets = load_cmake_presets(client.current_folder)
    assert "mytoolchain.cmake" in presets["configurePresets"][0]["toolchainFile"]


def test_cmake_toolchain_user_toolchain_from_dep():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                self.copy("*")
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", f)
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain.cmake !!!running!!!")'})
    client.run("create . toolchain/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            build_requires = "toolchain/0.1"
            generators = "CMakeToolchain"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": gen_cmakelists()}, clean_first=True)
    client.run("create . pkg/0.1@")
    assert "mytoolchain.cmake !!!running!!!" in client.out


def test_cmake_toolchain_without_build_type():
    # If "build_type" is not defined, toolchain will still be generated, it will not crash
    # Main effect is CMAKE_MSVC_RUNTIME_LIBRARY not being defined
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "arch").\
        with_generator("CMakeToolchain")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    toolchain = client.load("conan_toolchain.cmake")
    assert "CMAKE_MSVC_RUNTIME_LIBRARY" not in toolchain
    assert "CMAKE_BUILD_TYPE" not in toolchain


def test_cmake_toolchain_multiple_user_toolchain():
    """ A consumer consuming two packages that declare:
            self.conf_info["tools.cmake.cmaketoolchain:user_toolchain"]
        The consumer wants to use apply both toolchains in the CMakeToolchain.
        There are two ways to customize the CMakeToolchain (parametrized):
                1. Altering the context of the block (with_context = True)
                2. Using the t.blocks["user_toolchain"].user_toolchains = [] (with_context = False)
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                self.copy("*")
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", f)
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain1.cmake !!!running!!!")'})
    client.run("create . toolchain1/0.1@")
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain2.cmake !!!running!!!")'})
    client.run("create . toolchain2/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            tool_requires = "toolchain1/0.1", "toolchain2/0.1"
            generators = "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": gen_cmakelists()}, clean_first=True)
    client.run("create . pkg/0.1@")
    assert "mytoolchain1.cmake !!!running!!!" in client.out
    assert "mytoolchain2.cmake !!!running!!!" in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_no_warnings():
    """Make sure unitialized variables do not cause any warnings, passing -Werror=dev
    and --wanr-unitialized, calling "cmake" with conan_toolchain.cmake used to fail
    """
    # Issue https://github.com/conan-io/conan/issues/10288
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Conan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain", "CMakeDeps"
            requires = "dep/0.1"
        """)
    consumer = textwrap.dedent("""
       set(CMAKE_CXX_COMPILER_WORKS 1)
       set(CMAKE_CXX_ABI_COMPILED 1)
       project(MyHello CXX)
       cmake_minimum_required(VERSION 3.15)

       find_package(dep CONFIG REQUIRED)
       """)
    client.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                 "conanfile.py": conanfile,
                 "CMakeLists.txt": consumer})

    client.run("create dep")
    client.run("install .")
    client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=./conan_toolchain.cmake "
                       "-Werror=dev --warn-uninitialized")
    assert "Using Conan toolchain" in client.out
    # The real test is that there are no errors, it returns successfully


def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    ref = ConanFileReference.loads("zlib/1.2.11")
    client = TurboTestClient()
    client.run("new zlib/1.2.11 --template cmake_lib")
    cf = client.load("conanfile.py")
    pref = client.create(ref, conanfile=cf)
    p_folder = client.cache.package_layout(pref.ref).package(pref)
    assert not os.path.exists(os.path.join(p_folder, "mylibs"))
    assert os.path.exists(os.path.join(p_folder, "lib"))

    # Edit the cpp.package.libdirs and check if the library is placed anywhere else
    cf = client.load("conanfile.py")
    cf = cf.replace("cmake_layout(self)",
                    'cmake_layout(self)\n        self.cpp.package.libdirs = ["mylibs"]')

    pref = client.create(ref, conanfile=cf)
    p_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(p_folder, "mylibs"))
    assert not os.path.exists(os.path.join(p_folder, "lib"))
    b_folder = client.cache.package_layout(pref.ref).build(pref)
    layout_folder = "cmake-build-release" if platform.system() != "Windows" else "build"
    toolchain = client.load(os.path.join(b_folder, layout_folder, "conan", "conan_toolchain.cmake"))
    assert 'set(CMAKE_INSTALL_LIBDIR "mylibs")' in toolchain


def test_cmake_toolchain_definitions_complex_strings():
    # https://github.com/conan-io/conan/issues/11043
    client = TestClient(path_with_spaces=False)
    profile = textwrap.dedent(r'''
        include(default)
        [conf]
        tools.build:defines+=["escape=partially \"escaped\""]
        tools.build:defines+=["spaces=me you"]
        tools.build:defines+=["foobar=bazbuz"]
        tools.build:defines+=["answer=42"]
    ''')

    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout

        class Test(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*"
            settings = "os", "compiler", "arch", "build_type"

            def generate(self):
                tc = CMakeToolchain(self)
                tc.preprocessor_definitions["escape2"] = "partially \"escaped\""
                tc.preprocessor_definitions["spaces2"] = "me you"
                tc.preprocessor_definitions["foobar2"] = "bazbuz"
                tc.preprocessor_definitions["answer2"] = 42
                tc.preprocessor_definitions.release["escape_release"] = "release partially \"escaped\""
                tc.preprocessor_definitions.release["spaces_release"] = "release me you"
                tc.preprocessor_definitions.release["foobar_release"] = "release bazbuz"
                tc.preprocessor_definitions.release["answer_release"] = 42

                tc.preprocessor_definitions.debug["escape_debug"] = "debug partially \"escaped\""
                tc.preprocessor_definitions.debug["spaces_debug"] = "debug me you"
                tc.preprocessor_definitions.debug["foobar_debug"] = "debug bazbuz"
                tc.preprocessor_definitions.debug["answer_debug"] = 21
                tc.generate()

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        ''')

    main = textwrap.dedent("""
        #include <stdio.h>
        #define STR(x)   #x
        #define SHOW_DEFINE(x) printf("%s=%s", #x, STR(x))
        int main(int argc, char *argv[]) {
            SHOW_DEFINE(escape);
            SHOW_DEFINE(spaces);
            SHOW_DEFINE(foobar);
            SHOW_DEFINE(answer);
            SHOW_DEFINE(escape2);
            SHOW_DEFINE(spaces2);
            SHOW_DEFINE(foobar2);
            SHOW_DEFINE(answer2);
            #ifdef NDEBUG
            SHOW_DEFINE(escape_release);
            SHOW_DEFINE(spaces_release);
            SHOW_DEFINE(foobar_release);
            SHOW_DEFINE(answer_release);
            #else
            SHOW_DEFINE(escape_debug);
            SHOW_DEFINE(spaces_debug);
            SHOW_DEFINE(foobar_debug);
            SHOW_DEFINE(answer_debug);
            #endif
            return 0;
        }
        """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(Test CXX)
        set(CMAKE_CXX_STANDARD 11)
        add_executable(example src/main.cpp)
        """)

    client.save({"conanfile.py": conanfile, "profile": profile, "src/main.cpp": main,
                 "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("install . -pr=./profile -if=install")
    client.run("build . -if=install")
    exe = "cmake-build-release/example" if platform.system() != "Windows" else r"build\Release\example.exe"
    client.run_command(exe)
    assert 'escape=partially "escaped"' in client.out
    assert 'spaces=me you' in client.out
    assert 'foobar=bazbuz' in client.out
    assert 'answer=42' in client.out
    assert 'escape2=partially "escaped"' in client.out
    assert 'spaces2=me you' in client.out
    assert 'foobar2=bazbuz' in client.out
    assert 'answer2=42' in client.out
    assert 'escape_release=release partially "escaped"' in client.out
    assert 'spaces_release=release me you' in client.out
    assert 'foobar_release=release bazbuz' in client.out
    assert 'answer_release=42' in client.out

    client.run("install . -pr=./profile -if=install -s build_type=Debug")
    client.run("build . -if=install -s build_type=Debug")
    exe = "cmake-build-debug/example" if platform.system() != "Windows" else r"build\Debug\example.exe"
    client.run_command(exe)
    assert 'escape_debug=debug partially "escaped"' in client.out
    assert 'spaces_debug=debug me you' in client.out
    assert 'foobar_debug=debug bazbuz' in client.out
    assert 'answer_debug=21' in client.out
