import textwrap
import unittest

from parameterized import parameterized

from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer


class ConanGetTest(unittest.TestCase):

    def setUp(self):
        self.reference = "Hello0/0.1@lasote/channel"
        self.conanfile = textwrap.dedent('''
            from conans import ConanFile
            
            class HelloConan(ConanFile):
                name = "Hello0"
                version = "0.1"
                exports_sources = "path*"
                exports = "other*"
            ''')

        test_server = TestServer([], users={"lasote": "mypass"})
        servers = {"default": test_server}
        self.client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = {"conanfile.py": self.conanfile,
                 "path/to/exported_source": "1",
                 "other/path/to/exported": "2"}
        self.client.save(files)
        self.client.run("export . lasote/channel")
        self.client.run("install {} --build missing".format(self.reference))

    def test_get_local_reference(self):
        # Local search, dir list
        self.client.run('get {} .'.format(self.reference))
        self.assertEquals("""Listing directory '.':
 conanfile.py
 conanmanifest.txt
 other
""", self.client.user_io.out)

        self.client.run('get {} other --raw'.format(self.reference))
        self.assertEquals("path\n", self.client.user_io.out)

        self.client.run('get {} other/path --raw'.format(self.reference))
        self.assertEquals("to\n", self.client.user_io.out)

        self.client.run('get {} other/path/to'.format(self.reference))
        self.assertEquals("Listing directory 'other/path/to':\n exported\n",
                          self.client.user_io.out)

        self.client.run('get {} other/path/to/exported'.format(self.reference))
        self.assertEquals("2\n", self.client.user_io.out)

        # Local search, conanfile print
        self.client.run('get {} --raw'.format(self.reference))
        self.assertIn(self.conanfile, self.client.user_io.out)

    @parameterized.expand([(True, ), (False, )])
    def test_get_local_package_reference(self, use_pkg_reference):
        args_reference = self.reference if not use_pkg_reference else \
            "{}:{}".format(self.reference, NO_SETTINGS_PACKAGE_ID)
        args_package = " -p {}".format(NO_SETTINGS_PACKAGE_ID) if not use_pkg_reference else ""

        # Local search print package info
        self.client.run('get {} {} --raw'.format(args_reference, args_package))
        self.assertIn(textwrap.dedent("""
            [requires]
            
            
            [options]
            
            
            [full_settings]
            
            
            [full_requires]
            
            
            [full_options]
            
            
            [recipe_hash]
                07e4bf611af374672215a94d84146e2d
            
            """), self.client.user_io.out)

        # List package dir
        self.client.run('get {} "." {} --raw'.format(args_reference, args_package))
        self.assertEquals("conaninfo.txt\nconanmanifest.txt\n", self.client.user_io.out)

    def test_get_remote_reference(self):
        self.client.run('upload "Hello*" --all -c')

        # Remote search, dir list
        self.client.run('get {} . -r default --raw'.format(self.reference))
        self.assertIn("conan_export.tgz\nconan_sources.tgz\nconanfile.py\nconanmanifest.txt",
                      self.client.user_io.out)

        # Remote search, conanfile print
        self.client.run('get {} -r default --raw'.format(self.reference))
        self.assertIn(self.conanfile, self.client.user_io.out)

    @parameterized.expand([(True,), (False,)])
    def test_get_remote_package_reference(self, use_pkg_reference):
        args_reference = self.reference if not use_pkg_reference else \
            "{}:{}".format(self.reference, NO_SETTINGS_PACKAGE_ID)
        args_package = " -p {}".format(NO_SETTINGS_PACKAGE_ID) if not use_pkg_reference else ""

        self.client.run('upload "Hello*" --all -c')

        # List package dir
        self.client.run('get {} "." {} --raw -r default'.format(args_reference, args_package))
        self.assertEquals("conan_package.tgz\nconaninfo.txt\nconanmanifest.txt\n",
                          self.client.user_io.out)

    def test_not_found_reference(self):
        self.client.run('get {} "." -r default'.format(self.reference), assert_error=True)
        self.assertIn("Recipe {} not found".format(self.reference), self.client.user_io.out)

    @parameterized.expand([(True,), (False,)])
    def test_not_found_package_reference(self, use_pkg_reference):
        fake_package_id = "123123123123123"
        args_reference = self.reference if not use_pkg_reference else \
            "{}:{}".format(self.reference, fake_package_id)
        args_package = " -p {}".format(fake_package_id) if not use_pkg_reference else ""

        self.client.run('get {} "." -r default {}'.format(args_reference, args_package),
                        assert_error=True)
        self.assertIn("Package {}:{} not found".format(self.reference, fake_package_id),
                      self.client.user_io.out)

    def test_duplicated_input(self):
        """ Fail if given the full reference and the `-p` argument (even if they are equal)"""
        self.client.run('get {reference}:{pkg_id} -p {pkg_id}'.format(reference=self.reference,
                                                                      pkg_id=NO_SETTINGS_PACKAGE_ID),
                        assert_error=True)
        self.assertIn("Use a full package reference (preferred) or the `--package` "
                      "command argument, but not both.", self.client.out)
