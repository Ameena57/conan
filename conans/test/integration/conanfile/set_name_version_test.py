import os
import textwrap
import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conans.util.files import mkdir


class SetVersionNameTest(unittest.TestCase):

    @parameterized.expand([("", ), ("@user/channel", )])
    def test_set_version_name(self, user_channel):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = "pkg"
                def set_version(self):
                    self.version = "2.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . %s" % user_channel)
        self.assertIn("pkg/2.1%s: A new conanfile.py version was exported" % user_channel,
                      client.out)
        # installing it doesn't break
        client.run("install --reference=pkg/2.1%s --build=missing" % (user_channel or "@"))
        self.assertIn(f"pkg/2.1%s:{NO_SETTINGS_PACKAGE_ID} - Build" % user_channel,
                      client.out)
        client.run("install --reference=pkg/2.1%s --build=missing" % (user_channel or "@"))
        self.assertIn(f"pkg/2.1%s:{NO_SETTINGS_PACKAGE_ID} - Cache" % user_channel,
                      client.out)

        # Local flow should also work
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.1):", client.out)

    def test_set_version_name_file(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            class Lib(ConanFile):
                def set_name(self):
                    self.name = load("name.txt")
                def set_version(self):
                    self.version = load("version.txt")
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "pkg",
                     "version.txt": "2.1"})
        client.run("export . --user=user --channel=testing")
        self.assertIn("pkg/2.1@user/testing: A new conanfile.py version was exported", client.out)
        client.run("install --reference=pkg/2.1@user/testing --build=missing")
        self.assertIn(f"pkg/2.1@user/testing:{NO_SETTINGS_PACKAGE_ID} - Build",
                      client.out)
        client.run("install --reference=pkg/2.1@user/testing")
        self.assertIn(f"pkg/2.1@user/testing:{NO_SETTINGS_PACKAGE_ID} - Cache",
                      client.out)
        # Local flow should also work
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.1):", client.out)

    def test_set_version_name_errors(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = "pkg"
                def set_version(self):
                    self.version = "2.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=other --version=1.1 --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Package recipe with name other!=pkg", client.out)
        client.run("export .  --version=1.1 --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=2.1", client.out)
        # These are checked but match and don't conflict
        client.run("export . --version=2.1 --user=user --channel=testing")
        client.run("export . --name=pkg --version=2.1 --user=user --channel=testing")

        # Local flow should also fail
        client.run("install . --name=other --version=1.2", assert_error=True)
        self.assertIn("ERROR: Package recipe with name other!=pkg", client.out)

    def test_set_version_name_only_not_cli(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = self.name or "pkg"
                def set_version(self):
                    self.version = self.version or "2.0"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=other --version=1.1 --user=user --channel=testing")
        self.assertIn("other/1.1@user/testing: Exported", client.out)
        client.run("export .  --version=1.1 --user=user --channel=testing")
        self.assertIn("pkg/1.1@user/testing: Exported", client.out)
        client.run("export . --user=user --channel=testing")
        self.assertIn("pkg/2.0@user/testing: Exported", client.out)

        # Local flow should also work
        client.run("install . --name=other --version=1.2")
        self.assertIn("conanfile.py (other/1.2)", client.out)
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.0)", client.out)

    def test_set_version_name_crash(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = error
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in set_name() method, line 5", client.out)
        self.assertIn("name 'error' is not defined", client.out)
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           class Lib(ConanFile):
               def set_version(self):
                   self.version = error
           """)
        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in set_version() method, line 5", client.out)
        self.assertIn("name 'error' is not defined", client.out)

    def test_set_version_cwd(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, load
            class Lib(ConanFile):
                name = "pkg"
                def set_version(self):
                    self.version = load("version.txt")
            """)
        client.save({"conanfile.py": conanfile})
        mkdir(os.path.join(client.current_folder, "build"))
        with client.chdir("build"):
            client.save({"version.txt": "2.1"}, clean_first=True)
            client.run("export .. ")
            self.assertIn("pkg/2.1: A new conanfile.py version was exported", client.out)
