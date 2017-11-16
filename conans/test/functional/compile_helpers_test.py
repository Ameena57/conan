import os
import unittest

from conans.model.profile import Profile
from conans.model.scope import Scopes
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.util.files import save

conanfile_scope_env = """
from conans import ConanFile, ConfigureEnvironment

class AConan(ConanFile):
    settings = "os"
    requires = "Hello/0.1@lasote/testing"

    def build(self):
        self.run("SET" if self.settings.os=="Windows" else "env")
"""

conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package_info(self):
        self.env_info.PATH=["/path/to/my/folder"]
"""


class ProfilesEnvironmentTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def build_with_profile_test(self):
        self._create_profile("scopes_env", {},
                             {},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save({CONANFILE: conanfile_dep})
        self.client.run("export lasote/testing")

        self.client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        self.client.run("install --build=missing --pr scopes_env")
        self.client.run("build .")
        self.assertRegexpMatches(str(self.client.user_io.out), "PATH=['\"]*/path/to/my/folder")
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

    def _assert_env_variable_printed(self, name, value):
        self.assertIn("%s=%s" % (name, value), self.client.user_io.out)

    def _create_profile(self, name, settings, scopes=None, env=None):
        env = env or {}
        profile = Profile()
        profile._settings = settings or {}
        if scopes:
            profile.scopes = Scopes.from_list(["%s=%s" % (key, value) for key, value in scopes.items()])
        for varname, value in env.items():
            profile.env_values.add(varname, value)
        save(os.path.join(self.client.client_cache.profiles_path, name), "include(default)\n" + profile.dumps())
