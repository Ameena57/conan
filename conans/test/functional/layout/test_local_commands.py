import os
import re

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_local_static_generators_folder():
    """If we configure a generators folder in the layout, the generator files:
      - If belong to new generators: go to the specified folder: "my_generators"
      - If belong to old generators or txt: remains in the install folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type"))
    conan_file += """
    generators = "cmake", "CMakeToolchain"
    def layout(self):
        self.folders.build = "build-{}".format(self.settings.build_type)
        self.folders.generators = "{}/generators".format(self.folders.build)
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")

    old_install_folder = os.path.join(client.current_folder, "my_install")
    cmake_generator_path = os.path.join(old_install_folder, "conanbuildinfo.cmake")
    cmake_toolchain_generator_path = os.path.join(old_install_folder, "conan_toolchain.cmake")
    assert os.path.exists(cmake_generator_path)
    assert not os.path.exists(cmake_toolchain_generator_path)

    build_folder = os.path.join(client.current_folder, "build-Release")
    generators_folder = os.path.join(build_folder, "generators")
    cmake_generator_path = os.path.join(generators_folder, "conanbuildinfo.cmake")
    cmake_toolchain_generator_path = os.path.join(generators_folder, "conan_toolchain.cmake")
    assert not os.path.exists(cmake_generator_path)
    assert os.path.exists(cmake_toolchain_generator_path)


def test_local_dynamic_generators_folder():
    """If we configure a generators folder in the layout, the generator files:
      - If belong to new generators: go to the specified folder: "my_generators"
      - "txt" and old ones always to the install folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conan.tools.cmake import CMakeToolchain, CMake"))
    conan_file += """
    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()
    def layout(self):
        self.folders.build = "build-{}".format(self.settings.build_type)
        self.folders.generators = "{}/generators".format(self.folders.build)
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install -g cmake")

    old_install_folder = os.path.join(client.current_folder, "my_install")
    cmake_generator_path = os.path.join(old_install_folder, "conanbuildinfo.cmake")
    cmake_toolchain_generator_path = os.path.join(old_install_folder, "conan_toolchain.cmake")
    assert os.path.exists(cmake_generator_path)
    assert not os.path.exists(cmake_toolchain_generator_path)

    build_folder = os.path.join(client.current_folder, "build-Release")
    generators_folder = os.path.join(build_folder, "generators")
    cmake_generator_path = os.path.join(generators_folder, "conanbuildinfo.cmake")
    cmake_toolchain_generator_path = os.path.join(generators_folder, "conan_toolchain.cmake")
    assert not os.path.exists(cmake_generator_path)
    assert os.path.exists(cmake_toolchain_generator_path)


def test_no_layout_generators_folder():
    """If we don't configure a generators folder in the layout, the generator files:
      - all go to the install_folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conan.tools.cmake import CMakeToolchain, CMake"))
    conan_file += """
    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install -g cmake")

    old_install_folder = os.path.join(client.current_folder, "my_install")
    cmake_generator_path = os.path.join(old_install_folder, "conanbuildinfo.cmake")
    cmake_toolchain_generator_path = os.path.join(old_install_folder, "conan_toolchain.cmake")

    assert os.path.exists(cmake_generator_path)
    # In the install_folder
    assert os.path.exists(cmake_toolchain_generator_path)

    # But not in the base folder
    assert not os.path.exists(os.path.join(client.current_folder, "conan_toolchain.cmake"))


def test_local_build():
    """If we configure a build folder in the layout, the installed files in a "conan build ."
    go to the specified folder: "my_build"
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def layout(self):
        self.folders.generators = "my_generators"
        self.folders.build = "my_build"
    def build(self):
        self.output.warn("Generators folder: {}".format(self.folders.generators_folder))
        tools.save("build_file.dll", "bar")
"""
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    # FIXME: This should change to "build ." when "conan build" computes the graph
    client.run("build . -if=my_install")
    dll = os.path.join(client.current_folder, "my_build", "build_file.dll")
    assert os.path.exists(dll)


def test_local_build_change_base():
    """If we configure a build folder in the layout, the build files in a "conan build ."
    go to the specified folder: "my_build under the modified base one "common"
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def layout(self):
        self.folders.build = "my_build"
    def build(self):
        tools.save("build_file.dll", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=common")
    client.run("build . -if=common -bf=common")
    dll = os.path.join(client.current_folder, "common", "my_build", "build_file.dll")
    assert os.path.exists(dll)


def test_local_source():
    """If we configure a source folder in the layout, the downloaded files in a "conan source ."
    DON'T go to the specified folder: "my_source" but to the root source folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def layout(self):
        self.folders.source = "my_source"
    def source(self):
        tools.save("my_source/downloaded.h", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    # FIXME: This should change to "source ." when "conan source" computes the graph
    client.run("source .")
    header = os.path.join(client.current_folder, "my_source", "downloaded.h")
    assert os.path.exists(header)


def test_local_source_change_base():
    """If we configure a source folder in the layout, the source files in a "conan source ."
    DON'T go to the specified folder: "my_source under the modified base one "all_source"
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def layout(self):
        self.folders.source = "my_source"
    def source(self):
        tools.save("my_source/downloaded.h", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=common")
    client.run("source . -sf=common")
    header = os.path.join(client.current_folder, "common", "my_source", "downloaded.h")
    assert os.path.exists(header)


@pytest.mark.xfail(reason="Update to cache2.0")
def test_export_pkg():
    """The export-pkg, calling the "package" method, follows the layout if `cache_package_layout` """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    no_copy_source = True
    def layout(self):
        self.folders.source = "my_source"
        self.folders.build = "my_build"
    def source(self):
        tools.save("downloaded.h", "bar")
    def build(self):
        tools.save("library.lib", "bar")
        tools.save("generated.h", "bar")
    def package(self):
        self.output.warn("Source folder: {}".format(self.source_folder))
        self.output.warn("Build folder: {}".format(self.build_folder))
        self.output.warn("Package folder: {}".format(self.package_folder))
        self.copy("*.h")
        self.copy("*.lib")
    """

    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    client.run("source .")
    client.run("build . -if=my_install")
    client.run("export-pkg . lib/1.0@")
    package_id = re.search(r"lib/1.0: Package '(\S+)' created", str(client.out)).group(1)
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, package_id)
    sf = os.path.join(client.current_folder, "my_source")
    bf = os.path.join(client.current_folder, "my_build")
    pf = client.get_latest_pkg_layout(pref).package()

    assert "WARN: Source folder: {}".format(sf) in client.out
    assert "WARN: Build folder: {}".format(bf) in client.out
    assert "WARN: Package folder: {}".format(pf) in client.out

    # Check the artifacts packaged
    assert os.path.exists(os.path.join(pf, "generated.h"))
    assert os.path.exists(os.path.join(pf, "library.lib"))


@pytest.mark.xfail(reason="the conan package command was removed atm in Conan 2.0")
def test_export_pkg_local():
    """The export-pkg, without calling "package" method, with local package, follows the layout"""
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    no_copy_source = True
    def layout(self):
        self.folders.source = "my_source"
        self.folders.build = "my_build"
        self.folders.package = "my_package"
    def source(self):
        tools.save("downloaded.h", "bar")
    def build(self):
        tools.save("library.lib", "bar")
        tools.save("generated.h", "bar")
    def package(self):
        self.output.warn("Source folder: {}".format(self.source_folder))
        self.output.warn("Build folder: {}".format(self.build_folder))
        self.output.warn("Package folder: {}".format(self.package_folder))
        self.copy("*.h")
        self.copy("*.lib")
    """

    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    client.run("source .")
    client.run("build . -if=my_install")
    # client.run("package . -if=my_install")
    sf = os.path.join(client.current_folder, "my_source")
    bf = os.path.join(client.current_folder, "my_build")
    # pf = os.path.join(client.current_folder, "my_package")
    assert "WARN: Source folder: {}".format(sf) in client.out
    assert "WARN: Build folder: {}".format(bf) in client.out
    # assert "WARN: Package folder: {}".format(pf) in client.out

    client.run("export-pkg . lib/1.0@ -if=my_install -pf=my_package")
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
    pf_cache = client.get_latest_pkg_layout(pref).package()

    # Check the artifacts packaged, THERE IS NO "my_package" in the cache
    assert "my_package" not in pf_cache
    assert os.path.exists(os.path.join(pf_cache, "generated.h"))
    assert os.path.exists(os.path.join(pf_cache, "library.lib"))

    # Doing a conan create: Same as export-pkg, there is "my_package" in the cache
    client.run("create . lib/1.0@")
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
    pf_cache = client.get_latest_pkg_layout(pref).package()
    assert "my_package" not in pf_cache
    assert os.path.exists(os.path.join(pf_cache, "generated.h"))
    assert os.path.exists(os.path.join(pf_cache, "library.lib"))


@pytest.mark.xfail(reason="Update to cache2.0")
def test_imports():
    """The 'conan imports' follows the layout"""
    client = TestClient()
    # Hello to be reused
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    no_copy_source = True
    def build(self):
        tools.save("library.dll", "bar")
        tools.save("generated.h", "bar")
    def package(self):
        self.copy("*.h")
        self.copy("*.dll")
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . hello/1.0@")

    # Consumer of the hello importing the shared
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    no_copy_source = True
    requires = "hello/1.0"
    def layout(self):
        self.folders.imports = "my_imports"
    def imports(self):
        self.output.warn("Imports folder: {}".format(self.imports_folder))
        self.copy("*.dll")
    """

    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    client.run("imports .")

    imports_folder = os.path.join(client.current_folder, "my_imports")
    dll_path = os.path.join(imports_folder, "library.dll")

    assert "WARN: Imports folder: {}".format(imports_folder) in client.out
    assert os.path.exists(dll_path)

    # If we do a conan create, the imports folder is used also in the cache
    client.run("create . foo/1.0@")
    package_id = re.search(r"foo/1.0:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("foo/1.0@")
    pref = PackageReference(ref, package_id)
    bfolder = client.get_latest_pkg_layout(pref).build()
    imports_folder = os.path.join(bfolder, "my_imports")
    assert "WARN: Imports folder: {}".format(imports_folder) in client.out
