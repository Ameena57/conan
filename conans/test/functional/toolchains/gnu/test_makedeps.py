import textwrap

import platform
import pytest

from conans.test.assets.autotools import gen_makefile
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient
from conan.tools.gnu.makedeps import CONAN_MAKEFILE_FILENAME


@pytest.mark.tool("make" if platform.system() != "Windows" else "msys2")
def test_make_deps_definitions_escape():
    """
    MakeDeps has to escape the definitions properly.
    """
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("USER_CONFIG=\"user_config.h\"")
                self.cpp_info.defines.append('OTHER="other.h"')
                self.cpp_info.cflags.append("flag1=\"my flag1\"")
                self.cpp_info.cxxflags.append('flag2="my flag2"')
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . --name=hello --version=0.1.0")
    client.run("install --requires=hello/0.1.0 --build=missing -g MakeDeps")
    client.run_command(f"make --print-data-base -f {CONAN_MAKEFILE_FILENAME}", assert_error=True)
    assert r'CONAN_CXXFLAGS_HELLO = flag2=\"my flag2\"' in client.out
    assert r'CONAN_CFLAGS_HELLO = flag1=\"my flag1\"' in client.out
    assert r'CONAN_DEFINES_HELLO = $(CONAN_DEFINE_FLAG)USER_CONFIG="user_config.h" $(CONAN_DEFINE_FLAG)OTHER="other.h"' in client.out


def test_makedeps_with_tool_requires():
    """
    MakeDeps has to create any test requires to be declared on the recipe.
    """
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.libs = ["libname"]
        ''')
    client = TestClient(path_with_spaces=False)
    with client.chdir("lib"):
        client.save({"conanfile.py": conanfile.replace("libname", "hello")})
        client.run("create . --name=hello --version=0.1.0 -tf=\"\"")
    with client.chdir("test"):
        client.save({"conanfile.py": conanfile.replace("libname", "test")})
        client.run("create . --name=test --version=0.1.0 -tf=\"\"")
    with client.chdir("tool"):
        client.save({"conanfile.py": conanfile.replace("libname", "tool")})
        client.run("create . --name=tool --version=0.1.0 -tf=\"\"")
    # Create library having build and test requires
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.test_requires('hello/0.1.0')
                self.test_requires('test/0.1.0')
                self.tool_requires('tool/0.1.0')
        ''')
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g MakeDeps")
    content = client.load(CONAN_MAKEFILE_FILENAME)
    assert "CONAN_NAME_TEST" in content
    assert "CONAN_NAME_HELLO" in content
    assert "CONAN_NAME_TOOL" not in content


@pytest.mark.tool("msys2")
@pytest.mark.tool("mingw64")
def test_makedeps_with_makefile_build():
    """
    Build a small application using MakeDeps generator
    """
    client = TestClient(path_with_spaces=False)
    with client.chdir("lib"):
        client.save({"Makefile": gen_makefile(libs=["hello"]),
                    "hello.cpp": gen_function_cpp(name="hello", includes=["hello"], calls=["hello"]),
                    "hello.h": gen_function_h(name="hello"),
                    "conanfile.py": textwrap.dedent(r'''
                    from conan import ConanFile
                    from conan.tools.gnu import Autotools
                    from conan.tools.files import copy
                    import os
                    class PackageConan(ConanFile):
                        generators = "AutotoolsToolchain"
                        exports_sources = ("Makefile", "hello.cpp", "hello.h")
                        settings = "os", "arch", "compiler"

                        def configure(self):
                            self.win_bash = self.settings.os == "Windows"

                        def build(self):
                            Autotools(self).make()

                        def package(self):
                            copy(self, "libhello.a", src=self.build_folder, dst=os.path.join(self.package_folder, "lib"))
                            copy(self, "hello.h", src=self.source_folder, dst=os.path.join(self.package_folder, "include"))

                        def package_info(self):
                            self.cpp_info.libs = ["hello"]
                    ''')
                     })
        client.run('create . --name=hello --version=0.1.0 -c tools.microsoft.bash:subsystem=msys2 -c tools.microsoft.bash:path=bash')
    with client.chdir("app"):
        client.run("install --requires=hello/0.1.0 -pr:b=default -pr:h=default -g MakeDeps -of build")
        client.save({"Makefile": textwrap.dedent('''
            include build/conandeps.mk
            CXXFLAGS            += $(CONAN_CXXFLAGS)
            CPPFLAGS            += $(addprefix -I, $(CONAN_INCLUDE_DIRS))
            CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
            LDFLAGS             += $(addprefix -L, $(CONAN_LIB_DIRS))
            LDLIBS              += $(addprefix -l, $(CONAN_LIBS))
            EXELINKFLAGS        += $(CONAN_EXELINKFLAGS)

            all:
            \t$(CXX) main.cpp $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) $(LDLIBS) $(EXELINKFLAGS) -o main
            '''),
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
            })
        client.run_command("make -f Makefile")
