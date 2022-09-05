import unittest
from parameterized import parameterized
from textwrap import dedent

from conans.test.utils.tools import TestClient


class CppStdMinimumVersionTests(unittest.TestCase):

    CONANFILE = dedent("""
        import os
        from conans import ConanFile
        from conans.tools import check_min_cppstd, valid_min_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"

            def configure(self):
                check_min_cppstd(self, "17", False)
                self.output.info("valid standard")
                assert valid_min_cppstd(self, "17", False)
        """)

    PROFILE = dedent("""
        [settings]
        compiler=gcc
        compiler.version=9
        compiler.libcxx=libstdc++
        {}
        """)

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE})

    @parameterized.expand(["17", "gnu17"])
    def test_cppstd_from_settings(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile":  profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    @parameterized.expand(["11", "gnu11"])
    def test_invalid_cppstd_from_settings(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (%s) is lower than the required C++ "
                      "standard (17)." % cppstd, self.client.out)


def test_header_only_check_min_cppstd():

    conanfile = dedent("""
        import os
        from conan import ConanFile
        from conan.tools.build import check_min_cppstd, valid_min_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"
            def package_id(self):
                self.info.clear()
            def validate(self):
                if self.info.settings.compiler.cppstd:
                    check_min_cppstd(self, "11")
            def compatibility(self):
                check_min_cppstd(self, "11")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s compiler.cppstd=11")
    client.run("install fake/0.1@ -s compiler.cppstd=14")
    print(client.out)
