import unittest

from conans.test.utils.tools import TestClient


class PreExportTest(unittest.TestCase):

    def load_from_file_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, load
import os
class Pkg(ConanFile):
    name = "MyPkg"

    def preexport(self):
        self.version = load(os.path.join(self.recipe_folder, "version.txt"))
"""
        client.save({"conanfile.py": conanfile,
                     "version.txt": "1.2.3"})
        client.run("export . user/channel")
        self.assertIn("MyPkg/1.2.3@user/channel: A new conanfile.py version was exported",
                      client.out)
        client.run("create . user/channel")
        self.assertIn("MyPkg/1.2.3@user/channel: Calling package()", client.out)

    def basic_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):

    def preexport(self):
        self.name = "MyPkg"
        self.version = "1.2.3"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . user/channel")
        self.assertIn("MyPkg/1.2.3@user/channel: A new conanfile.py version was exported",
                      client.out)
        client.run("create . user/channel")
        self.assertIn("MyPkg/1.2.3@user/channel: Calling package()", client.out)
