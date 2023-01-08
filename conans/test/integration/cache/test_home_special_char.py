import os

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient

import textwrap


def test_home_special_chars():
    """ the path with special characters is creating a conanbuild.bat that fails
    """
    path_chars = "päthñç$"
    cache_folder = os.path.join(temp_folder(), path_chars)
    current_folder = os.path.join(temp_folder(), path_chars)
    c = TestClient(cache_folder, current_folder)

    conan_file = textwrap.dedent("""
        from conan import ConanFile

        class App(ConanFile):
            name="failure"
            version="0.1"
            settings = 'os', 'arch', 'compiler', 'build_type'
            generators = "MSBuildToolchain"

            def build(self):
                self.run("git --version")
        """)

    c.save({"conanfile.py": conan_file})
    c.run("create .")
    assert path_chars in c.out
