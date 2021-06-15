import os
import unittest

import pytest

from conans.client import tools
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir, rmdir

conanfile = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    exports_sources = "*"
    generators = "cmake"

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")
        save("subdir/myartifact2.lib", "artifact2 contents!")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
'''


class DevInSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'subdir', 'conaninfo.txt',
                                 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))
        self.assertEqual(load(os.path.join(folder, "myartifact.lib")),
                         "artifact contents!")
        self.assertEqual(load(os.path.join(folder, "subdir/myartifact2.lib")),
                         "artifact2 contents!")

    def test_parallel_folders(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        build_folder = os.path.join(client.current_folder, "build")
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(repo_folder)
        mkdir(build_folder)
        mkdir(package_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ../recipe")
        client.run("build ../recipe")

        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=../build")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.cache.package_layout(ref).packages()
        self._assert_pkg(cache_package_folder)

    def test_insource_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.run("install .")
        client.run("build .")
        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=.")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.cache.package_layout(ref).packages()
        self._assert_pkg(cache_package_folder)

    def test_child_build(self):
        client = TestClient()
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(build_folder, "package")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..")

        client.current_folder = build_folder
        client.run("export-pkg .. Pkg/0.1@lasote/testing --source-folder=.. ")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.cache.package_layout(ref).packages()
        self._assert_pkg(cache_package_folder)


conanfile_out = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    generators = "cmake"

    def source(self):
        save("file.h", "file_h_contents!")

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
'''


class DevOutSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'conaninfo.txt', 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))

    def test_parallel_folders(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        src_folder = os.path.join(client.current_folder, "src")
        build_folder = os.path.join(client.current_folder, "build")
        package_folder = os.path.join(build_folder, "package")
        mkdir(repo_folder)
        mkdir(src_folder)
        mkdir(build_folder)
        mkdir(package_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile_out})

        client.current_folder = build_folder
        client.run("install ../recipe")
        client.current_folder = src_folder
        client.run("install ../recipe")
        client.run("source ../recipe")
        client.current_folder = build_folder
        client.run("build ../recipe --source-folder=../src")
        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=../build -sf=../src")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.cache.package_layout(ref).packages()
        self._assert_pkg(cache_package_folder)

    def test_insource_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile_out})

        client.run("install .")
        client.run("source .")
        client.run("build . ")

        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=.")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.cache.package_layout(ref).packages()
        self._assert_pkg(cache_package_folder)

    def test_child_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(build_folder, "package")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile_out})

        client.current_folder = build_folder
        client.run("install ..")
        client.run("source ..")
        client.run("build .. --source-folder=.")
        client.current_folder = repo_folder

        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=./build")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.cache.package_layout(ref).packages()
        self._assert_pkg(cache_package_folder)

    @pytest.mark.tool_compiler
    def test_build_local_different_folders(self):
        # Real build, needed to ensure that the generator is put in the correct place and
        # cmake finds it, using an install_folder different from build_folder
        client = TestClient()
        client.run("new lib/1.0")
        # FIXME: this test, so it doesn't need to clone from github
        client.run("source . --source-folder src")

        # Patch the CMakeLists to include the generator file from a different folder
        install_dir = os.path.join(client.current_folder, "install_x86_64")
        tools.replace_in_file(os.path.join(client.current_folder, "src", "hello", "CMakeLists.txt"),
                              "${CMAKE_BINARY_DIR}/conanbuildinfo.cmake",
                              '"%s/conanbuildinfo.cmake"' % install_dir.replace("\\", "/"),
                              output=client.out)

        client.run("install . --install-folder install_x86_64 -s arch=x86_64")
        client.run("build . --build-folder build_x86_64 --install-folder '%s' "
                   "--source-folder src" % install_dir)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build_x86_64", "lib")))
