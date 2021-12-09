import os
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, GenConanfile


class RemoveOutdatedTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_remove_query(self):
        test_server = TestServer(users={"admin": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    settings = "os"
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . Test/0.1@lasote/testing -s os=Windows")
        client.run("create . Test/0.1@lasote/testing -s os=Linux")
        client.save({"conanfile.py": conanfile.replace("settings", "pass #")})
        client.run("create . Test2/0.1@lasote/testing")
        client.run("upload * --all --confirm -r default")
        for remote in ("", "-r=default"):
            client.run("remove Test/0.1@lasote/testing -q=os=Windows -f %s" % remote)
            client.run("search Test/0.1@lasote/testing %s" % remote)
            self.assertNotIn("os: Windows", client.out)
            self.assertIn("os: Linux", client.out)

            client.run("remove Test2/0.1@lasote/testing -q=os=Windows -f %s" % remote)
            client.run("search Test2/0.1@lasote/testing %s" % remote)
            self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
            client.run("remove Test2/0.1@lasote/testing -q=os=None -f %s" % remote)
            client.run("search Test2/0.1@lasote/testing %s" % remote)
            self.assertNotIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
            self.assertIn("There are no packages", client.out)


conaninfo = '''
[settings]
    arch=x64
    os=Windows
    compiler=Visual Studio
    compiler.version=8.%s
[options]
    use_Qt=True
[full_requires]
  hello2/0.1@lasote/stable:11111
  OpenSSL/2.10@lasote/testing:2222
  HelloInfo1/0.45@myuser/testing:33333
[recipe_revision]
'''


class RemoveWithoutUserChannel(unittest.TestCase):

    def setUp(self):
        self.test_server = TestServer(users={"lasote": "password"},
                                      write_permissions=[("lib/1.0@*/*", "lasote")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["lasote", "password"])

    def test_local(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . lib/1.0@")
        latest_rrev = self.client.cache.get_latest_recipe_reference(RecipeReference.loads("lib/1.0"))
        ref_layout = self.client.cache.ref_layout(latest_rrev)
        pkg_ids = self.client.cache.get_package_references(latest_rrev)
        latest_prev = self.client.cache.get_latest_package_reference(pkg_ids[0])
        pkg_layout = self.client.cache.pkg_layout(latest_prev)
        self.client.run("remove lib/1.0 -f")
        self.assertFalse(os.path.exists(ref_layout.base_folder))
        self.assertFalse(os.path.exists(pkg_layout.base_folder))

    def test_remote(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . lib/1.0@")
        self.client.run("upload lib/1.0 -r default -c --all")
        self.client.run("remove lib/1.0 -f")
        # we can still install it
        self.client.run("install --reference=lib/1.0@")
        self.assertIn("lib/1.0: Retrieving package", self.client.out)
        self.client.run("remove lib/1.0 -f")

        # Now remove remotely
        self.client.run("remove lib/1.0 -f -r default")
        self.client.run("install --reference=lib/1.0@", assert_error=True)

        self.assertIn("Unable to find 'lib/1.0' in remotes", self.client.out)


class RemovePackageRevisionsTest(unittest.TestCase):

    NO_SETTINGS_RREF = "f3367e0e7d170aa12abccb175fee5f97"

    def setUp(self):
        self.test_server = TestServer(users={"user": "password"},
                                      write_permissions=[("foobar/0.1@*/*", "user")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["user", "password"])

    def test_remove_local_package_id_argument(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved
            Package ID is a separated argument: <package>#<rref> -p <pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Cache", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: a397cb03d51fb3b129c78d2968e2676f", self.client.out)

        self.client.run("remove -f foobar/0.1@user/testing#{} -p {}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Missing", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: None", self.client.out)

    def test_remove_local_package_id_reference(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Cache", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: a397cb03d51fb3b129c78d2968e2676f", self.client.out)

        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Missing", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: None", self.client.out)

    def test_remove_duplicated_package_id(self):
        """ The package ID must not be present in both -p argument and package reference
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("remove -f foobar/0.1@user/testing#{}:{} -p {}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID,
                                NO_SETTINGS_PACKAGE_ID), assert_error=True)
        self.assertIn("Use package ID only as -p argument or reference, not both", self.client.out)

    def test_remove_remote_package_id_reference(self):
        """ Remove remote package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("upload foobar/0.1@user/testing -r default -c --all")
        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Download", self.client.out)
        self.client.run("remove -f foobar/0.1@user/testing#{}:{} -r default"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Missing", self.client.out)
