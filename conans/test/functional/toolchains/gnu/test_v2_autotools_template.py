import platform
import re
import os
import shutil

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")

    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    client.run("export-pkg . hello/0.1@ -if=install")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    pref = PackageReference(ConanFileReference.loads("hello/0.1"), package_id)
    package_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # Create + shared works
    client.save({}, clean_first=True)
    client.run("new hello/0.1 --template=autotools_lib")
    client.run("create . -o hello:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out
    if platform.system() == "Darwin":
        client.run_command("otool -l test_package/build-release/main")
        assert "libhello.0.dylib" in client.out
    else:
        client.run_command("ldd test_package/build-release/main")
        assert "libhello.so.0" in client.out


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new greet/0.1 --template=autotools_exe")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_relocatable_libs_darwin():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")
    client.run("create . -o hello:shared=True")
    package_id = re.search(r"Package (\S+)", str(client.out)).group(1)
    package_id = package_id.replace("'", "")
    pref = PackageReference(ConanFileReference.loads("hello/0.1"), package_id)
    package_folder = client.cache.package_layout(pref.ref).package(pref)
    dylib = os.path.join(package_folder, "lib", "libhello.0.dylib")
    if platform.system() == "Darwin":
        client.run_command("otool -l {}".format(dylib))
        assert "@rpath/libhello.0.dylib" in client.out
        client.run_command("otool -l {}".format("test_package/build-release/main"))
        assert package_folder in client.out
        assert "@executable_path" in client.out

    # will work because rpath set
    client.run_command("test_package/build-release/main")
    assert "hello/0.1: Hello World Release!" in client.out

    # move to another location so that the path set in the rpath does not exist
    # then the execution should fail
    shutil.move(os.path.join(package_folder, "lib"), os.path.join(client.current_folder, "tempfolder"))
    # will fail because rpath does not exist
    client.run_command("test_package/build-release/main", assert_error=True)
    assert "Library not loaded: @rpath/libhello.0.dylib" in client.out

    # move the dylib to the folder where the executable is
    # should work because the @executable_path set in the rpath
    shutil.move(os.path.join(client.current_folder, "tempfolder", "libhello.0.dylib"),
                os.path.join(client.current_folder, "test_package", "build-release"))
    shutil.move(os.path.join(client.current_folder, "tempfolder", "libhello.dylib"),
                os.path.join(client.current_folder, "test_package", "build-release"))
    client.run_command("test_package/build-release/main")
    assert "hello/0.1: Hello World Release!" in client.out
