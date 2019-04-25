import json
import os
import textwrap
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load
from conans.test.utils.conanfile import TestConanFile


class GraphLockErrorsTest(unittest.TestCase):
    def missing_lock_error_test(self):
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("install . --lock", assert_error=True)
        self.assertIn("ERROR: Failed to load graphinfo file in install-folder", client.out)


class GraphLockVersionRangeTest(unittest.TestCase):
    consumer = TestConanFile("PkgB", "0.1", requires=["PkgA/[>=0.1]@user/channel"])
    pkg_b_revision = "180919b324d7823f2683af9381d11431"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"

    def setUp(self):
        client = TestClient()
        self.client = client
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py": str(self.consumer)})
        client.run("install .")

        self._check_lock("PkgB/0.1@None/None")

        # If we create a new PkgA version
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.2"))})
        client.run("create . PkgA/0.2@user/channel")
        client.save({"conanfile.py": str(self.consumer)})

    def _check_lock(self, ref_b):
        lock_file = load(os.path.join(self.client.current_folder, "graph_info.json"))
        lock_file_json = json.loads(lock_file)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1@user/channel#b55538d56afb03f068a054f11310ce5a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#6d56ca1040e37a13b75bc286f3e1a5ad",
                      lock_file)
        self.assertIn('"%s:%s"' % (str(ref_b), self.pkg_b_id), lock_file)

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        self.assertIn("PkgA/0.2@user/channel", client.out)
        self.assertNotIn("PkgA/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        # To use the stored graph_info.json, it has to be explicit in "--install-folder"
        client.run("install . -g=cmake --lock")
        self._check_lock("PkgB/0.1@None/None")

        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2@user/channel", client.out)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("PkgA/0.1/user/channel", cmake)
        self.assertNotIn("PkgA/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --lock")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)

    def export_lock_test(self):
        # locking a version range at export
        self.client.run("export . user/channel --lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)

    def create_lock_test(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@user/channel --lock")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . PkgB/0.1@user/channel --lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)


class GraphLockBuildRequireVersionRangeTest(GraphLockVersionRangeTest):
    consumer = TestConanFile("PkgB", "0.1", build_requires=["PkgA/[>=0.1]@user/channel"])
    pkg_b_revision = "4e4df18e796d2a1bfc7bbce7f8865ecd"
    pkg_b_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"


class GraphLockRevisionTest(unittest.TestCase):
    pkg_b_revision = "9b64caa2465f7660e6f613b7e87f0cd7"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"

    def setUp(self):
        test_server = TestServer(users={"user": "user"})
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("user", "user")]})
        # Important to activate revisions
        client.run("config set general.revisions_enabled=True")
        self.client = client
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("create . PkgA/0.1@user/channel")
        client.run("upload PkgA/0.1@user/channel --all")

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                name = "PkgB"
                version = "0.1"
                requires = "PkgA/0.1@user/channel"
                def build(self):
                    self.output.info("BUILD DEP LIBS: %s!!" % ",".join(self.deps_cpp_info.libs))
                def package_info(self):
                    self.output.info("PACKAGE_INFO DEP LIBS: %s!!"
                                     % ",".join(self.deps_cpp_info.libs))
            """)
        client.save({"conanfile.py": str(consumer)})
        client.run("install .")

        self._check_lock("PkgB/0.1@None/None")

        # If we create a new PkgA revision, for example adding info
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1", info=True))})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": str(consumer)})

    def _check_lock(self, ref_b):
        lock_file = load(os.path.join(self.client.current_folder, "graph_info.json"))
        lock_file_json = json.loads(lock_file)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1@user/channel#b55538d56afb03f068a054f11310ce5a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#6d56ca1040e37a13b75bc286f3e1a5ad",
                      lock_file)
        self.assertIn('"%s:%s"' % (str(ref_b), self.pkg_b_id), lock_file)

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        client.run("build . -if=tmp")
        self.assertIn("conanfile.py (PkgB/0.1@None/None): BUILD DEP LIBS: mylibPkgA0.1lib!!",
                      client.out)

        # Locked install will use PkgA/0.1
        # This is a bit weird, that is necessary to force the --update the get the rigth revision
        client.run("install . -g=cmake --lock --update")
        self._check_lock("PkgB/0.1@None/None")
        client.run("build .")
        self.assertIn("conanfile.py (PkgB/0.1@None/None): BUILD DEP LIBS: !!", client.out)

        # Info also works
        client.run("info . --lock")
        self.assertIn("Revision: b55538d56afb03f068a054f11310ce5a", client.out)

    def export_lock_test(self):
        # locking a version range at export
        self.client.run("export . user/channel --lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)

    def create_lock_test(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@user/channel --lock --update")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . PkgB/0.1@user/channel --lock --update")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)


class GraphLockPythonRequiresTest():

    def python_requires_lock_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            var = 42
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = textwrap.dedent("""
            from conans import ConanFile, python_requires
            dep = python_requires("Tool/[>=0.1]@user/channel")

            class Pkg(ConanFile):
                def build(self):
                    self.output.info("VAR=%s" % dep.var)
            """)
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.1@user/channel", client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("Tool/0.1@user/channel", lock_file)

        client.run("build .")
        self.assertIn("conanfile.py: VAR=42", client.out)

        # If we create a new Tool version
        client.save({"conanfile.py": conanfile.replace("42", "111")})
        client.run("export . Tool/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        # Make sure to use temporary if to not change graph_info.json
        client.run("install . -if=tmp")
        self.assertIn("Tool/0.2@user/channel", client.out)
        client.run("build .")
        self.assertIn("conanfile.py: VAR=111", client.out)

        # Locked create will use Tool/0.1
        # Updating the root in the graph-info file
        client.run("install . --lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("Tool/0.1@user/channel", lock_file)
        self.assertNotIn("Tool/0.2@user/channel", lock_file)

        client.run("create . Pkg/0.1@user/channel --lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
