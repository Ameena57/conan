import platform
import re
import os
import shutil
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, TestServer


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_lib -d name=hello -d version=0.1")

    # Local flow works
    client.run("install .")
    client.run("build .")

    client.run("export-pkg .")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    ref = RecipeReference.loads("hello/0.1")
    pref = client.get_latest_package_reference(ref, package_id)
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))
    assert os.path.exists(os.path.join(package_folder, "lib", "libhello.a"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # Create + shared works
    client.save({}, clean_first=True)
    client.run("new autotools_lib -d name=hello -d version=0.1")
    client.run("create . -o hello/*:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out
    if platform.system() == "Darwin":
        client.run_command("otool -l test_package/test_output/build-release/main")
        assert "libhello.0.dylib" in client.out
    else:
        client.run_command("ldd test_package/test_output/build-release/main")
        assert "libhello.so.0" in client.out


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_exe -d name=greet -d version=0.1")
    # Local flow works
    client.run("install .")
    client.run("build .")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_relocatable_libs_darwin():
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_lib -d name=hello -d version=0.1")
    client.run("create . -o hello/*:shared=True")

    package_id = re.search(r"Package (\S+) created", str(client.out)).group(1)
    package_id = package_id.replace("'", "")
    ref = RecipeReference.loads("hello/0.1")
    pref = client.get_latest_package_reference(ref, package_id)
    package_folder = client.get_latest_pkg_layout(pref).package()

    dylib = os.path.join(package_folder, "lib", "libhello.0.dylib")
    if platform.system() == "Darwin":
        client.run_command("otool -l {}".format(dylib))
        assert "@rpath/libhello.0.dylib" in client.out
        client.run_command("otool -l {}".format("test_package/test_output/build-release/main"))
        assert package_folder in client.out

    # will work because rpath set
    client.run_command("test_package/test_output/build-release/main")
    assert "hello/0.1: Hello World Release!" in client.out

    # move to another location so that the path set in the rpath does not exist
    # then the execution should fail
    shutil.move(os.path.join(package_folder, "lib"), os.path.join(client.current_folder, "tempfolder"))
    # will fail because rpath does not exist
    client.run_command("test_package/test_output/build-release/main", assert_error=True)
    assert "Library not loaded: @rpath/libhello.0.dylib" in client.out

    # Use DYLD_LIBRARY_PATH and should run
    client.run_command("DYLD_LIBRARY_PATH={} test_package/test_output/build-release/main".format(os.path.join(client.current_folder, "tempfolder")))
    assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_relocatable_libs_darwin_downloaded():
    client = TestClient(default_server_user=True, path_with_spaces=False)
    client2 = TestClient(servers=client.servers, path_with_spaces=False)
    assert client2.cache_folder != client.cache_folder
    client.run("new autotools_lib -d name=hello -d version=0.1")
    client.run("create . -o hello/*:shared=True -tf=None")
    client.run("upload hello/0.1 -c -r default")
    client.run("remove * -f")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools
        from conan.tools.layout import basic_layout

        class GreetConan(ConanFile):
            name = "greet"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def requirements(self):
                self.requires("hello/0.1")

            def layout(self):
                basic_layout(self)

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()
        """)

    main = textwrap.dedent("""
        #include "hello.h"
        int main() { hello(); }
        """)

    makefileam = textwrap.dedent("""
        bin_PROGRAMS = greet
        greet_SOURCES = main.cpp
        """)

    configureac = textwrap.dedent("""
        AC_INIT([greet], [1.0], [])
        AM_INIT_AUTOMAKE([-Wall -Werror foreign])
        AC_PROG_CXX
        AM_PROG_AR
        LT_INIT
        AC_CONFIG_FILES([Makefile])
        AC_OUTPUT
        """)

    client2.save({"conanfile.py": conanfile,
                  "main.cpp": main,
                  "makefile.am": makefileam,
                  "configure.ac": configureac})

    client2.run("install . -o hello/*:shared=True -r default")
    client2.run("build . -o hello/*:shared=True -r default")
    client2.run_command("build-release/greet")
    assert "Hello World Release!" in client2.out
