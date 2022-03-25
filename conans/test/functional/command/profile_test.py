import os
import platform
import subprocess
import textwrap
import unittest

import pytest

from conans.client.conf.detect import detect_defaults_settings
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.tools import TestClient, redirect_output
from conans.util.env import environment_update
from conans.util.files import load, save
from conans.util.runners import check_output_runner


class TestProfile(unittest.TestCase):

    def test_list_empty(self):
        client = TestClient()
        client.run("profile list")
        self.assertIn("Profiles found in the cache:", client.out)

    def test_list(self):
        client = TestClient()
        profiles = ["default", "profile1", "profile2", "profile3",
                    "nested" + os.path.sep + "profile4",
                    "nested" + os.path.sep + "two" + os.path.sep + "profile5",
                    "nested" + os.path.sep + "profile6"]
        if platform.system() != "Windows":
            profiles.append("symlink_me" + os.path.sep + "profile7")
        for profile in profiles:
            save(os.path.join(client.cache.profiles_path, profile), "")

        if platform.system() != "Windows":
            os.symlink(os.path.join(client.cache.profiles_path, 'symlink_me'),
                       os.path.join(client.cache.profiles_path, 'link'))
            # profile7 will be shown twice because it is symlinked.
            profiles.append("link" + os.path.sep + "profile7")

        # Make sure local folder doesn't interact with profiles
        os.mkdir(os.path.join(client.current_folder, "profile3"))
        client.run("profile list")
        for p in profiles:
            assert p in client.out

        # Test profile list json file
        # FIXME: Json cannot be captured from tests?
        # client.run("profile list --format=json > profiles_list.json")
        # json_content = client.load("profiles_list.json")
        # json_obj = json.loads(json_content)
        # self.assertEqual(list, type(json_obj))
        # self.assertEqual(profiles, json_obj)

    def test_show(self):
        client = TestClient()
        profile1 = textwrap.dedent("""
            [settings]
            os=Windows
            [options]
            MyOption=32
            [conf]
            tools.ninja:jobs=10
            tools.gnu.make:jobs=20
            """)
        save(os.path.join(client.cache.profiles_path, "profile1"), profile1)

        client.run("profile show -pr=profile1")
        self.assertIn("[settings]\nos=Windows", client.out)
        self.assertIn("MyOption=32", client.out)
        # self.assertIn("CC=/path/tomy/gcc_build", client.out)
        # self.assertIn("CXX=/path/tomy/g++_build", client.out)
        # self.assertIn("package:VAR=value", client.out)
        self.assertIn("tools.ninja:jobs=10", client.out)
        self.assertIn("tools.gnu.make:jobs=20", client.out)

    def test_missing_subarguments(self):
        client = TestClient()
        client.run("profile", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", client.out)


class DetectCompilersTest(unittest.TestCase):
    def test_detect_default_compilers(self):
        platform_default_compilers = {
            "Linux": "gcc",
            "Darwin": "apple-clang",
            "Windows": "msvc"
        }

        result = detect_defaults_settings()
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        platform_compiler = platform_default_compilers.get(platform.system(), None)
        if platform_compiler is not None:
            self.assertEqual(result.get("compiler", None), platform_compiler)

    @pytest.mark.tool("gcc")
    @pytest.mark.skipif(platform.system() != "Darwin", reason="only OSX test")
    def test_detect_default_in_mac_os_using_gcc_as_default(self):
        """
        Test if gcc in Mac OS X is using apple-clang as frontend
        """
        # See: https://github.com/conan-io/conan/issues/2231
        output = check_output_runner(["gcc", "--version"], stderr=subprocess.STDOUT)

        if "clang" not in output:
            # Not test scenario gcc should display clang in output
            # see: https://stackoverflow.com/questions/19535422/os-x-10-9-gcc-links-to-clang
            raise Exception("Apple gcc doesn't point to clang with gcc frontend anymore!")

        output = RedirectedTestOutput()  # Initialize each command
        with redirect_output(output):
            with environment_update({"CC": "gcc"}):
                result = detect_defaults_settings()
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        # No compiler should be detected
        self.assertIsNone(result.get("compiler", None))
        self.assertIn("gcc detected as a frontend using apple-clang", output)

    def test_profile_new(self):
        client = TestClient()

        client.run("profile detect --name=./MyProfile2")
        pr_path = os.path.join(client.current_folder, "MyProfile2")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "MyProfile2")))
        self.assertIn("os=", load(pr_path))

        client.run("profile detect --name=./MyProfile2", assert_error=True)
        self.assertIn("MyProfile2' already exists", client.out)
