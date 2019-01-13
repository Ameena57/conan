# coding=utf-8

import os
import re
import textwrap
import unittest

from conans.test.utils.tools import TestClient
from conans.util.files import load, save_files
from conans.client.cache import LAYOUTS_FOLDER


class LayoutTest(unittest.TestCase):

    def test_missing_layouts(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)

        client.save({"conanfile.py": conanfile})
        client.run("link . mytool/0.1@user/testing -l=missing")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install .", assert_error=True)
        self.assertIn("ERROR: Layout file not found: missing", client2.out)

    def test_repo_layouts(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)
        layout_repo = textwrap.dedent("""
            [includedirs]
            include_{}
            """)
        layout_cache = textwrap.dedent("""
            [{}:includedirs]
            include_{}
            """)
        layout_folder = os.path.join(client.base_folder, ".conan", LAYOUTS_FOLDER)
        save_files(layout_folder, {"layout_win_cache": layout_cache.format("*", "win_cache"),
                                   "layout_linux_cache": layout_cache.format("*", "linux_cache"),
                                   "layout_win_cache2": layout_cache.format("mytool", "win_cache2"),
                                   "layout_linux_cache2": layout_cache.format("mytool",
                                                                              "linux_cache2"),
                                   "layout_win_cache3": layout_repo.format("win_cache3"),
                                   "layout_linux_cache3": layout_repo.format("linux_cache3")})
        client.save({"conanfile.py": conanfile,
                     "layout_win": layout_repo.format("win"),
                     "layout_linux": layout_repo.format("linux")})
        client.run("link . mytool/0.1@user/testing")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake")
        self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
        cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
        include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
        self.assertTrue(include_dirs.endswith("include"))

        # Using the repo file layouts
        for layout in ("win", "linux", "win_cache", "linux_cache", "win_cache2", "linux_cache2",
                       "win_cache3", "linux_cache3"):
            client.run("link . mytool/0.1@user/testing -l=layout_%s" % layout)
            client2.run("install . -g cmake")
            self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
            cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % layout))
