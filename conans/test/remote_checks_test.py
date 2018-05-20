import unittest
from conans.test.utils.tools import TestClient, TestServer


class RemoteChecksTest(unittest.TestCase):

    def test_binary_defines_remote(self):
        servers = {"server1": TestServer(), "server2": TestServer(), "server3": TestServer()}
        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")],
                                                    "server3": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        client.run("upload Pkg* --all -r=server1 --confirm")
        client.run("upload Pkg* --all -r=server2 --confirm")

        # It takes the default remote
        client.run("remove * -f")
        client.run("remote list_ref")
        self.assertNotIn("Pkg", client.out)

        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Downloading conan_package.tgz", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server1", client.out)

        # Explicit remote also defines the remote
        client.run("remove * -f")
        client.run("remote list_ref")
        self.assertNotIn("Pkg", client.out)
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -r=server2")
        self.assertIn("Downloading conan_package.tgz", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)

        # But order fails!!!
        client.run("remove * -f")
        client.run("remove * -f -r=server1")
        client.run("export . Pkg/0.1@lasote/testing")
        error = client.run("install Pkg/0.1@lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)
        client.run("remote list_ref")
        self.assertNotIn("Pkg", client.out)

    def test_binaries_from_different_remotes(self):
        servers = {"server1": TestServer(), "server2": TestServer(), "server3": TestServer()}
        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"opt": [1, 2, 3]}
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing -o Pkg:opt=1")
        client.run("upload Pkg* --all -r=server1 --confirm")
        client.run("remove * -p -f")
        client.run("create . Pkg/0.1@lasote/testing -o Pkg:opt=2")
        client.run("upload Pkg* --all -r=server2 --confirm")
        client.run("remove * -p -f")
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server1", client.out)
        # Trying to install from another remote fails
        error = client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)
        # Also update fails
        error = client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2 -u", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)
        # Build outdated
        error = client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2 --build=outdated",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)

        # If the remote reference is dissasociated, it works
        client.run("remote remove_ref Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2")
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)
