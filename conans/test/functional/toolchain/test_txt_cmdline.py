import textwrap
import unittest

import pytest
from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient


@attr("toolchain")
@pytest.mark.toolchain
class TestTxtCommandLine(unittest.TestCase):

    def test_declarative(self):
        conanfile = textwrap.dedent("""
            [generators]
            CMakeToolchain
            MesonToolchain
            MakeToolchain
            MSBuildToolchain
            """)
        client = TestClient()
        client.save({"conanfile.txt": conanfile})
        client.run("install .")
        self._check(client)

    def _check(self, client):
        self.assertIn("conanfile.txt: Generating toolchain files", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)
        toolchain = client.load("conantoolchain.props")
        self.assertIn("<?xml version", toolchain)
        toolchain = client.load("conan_toolchain.mak")
        self.assertIn("# Conan generated toolchain file", toolchain)
        toolchain = client.load("conan_meson_native.ini")
        self.assertIn("[project options]", toolchain)

    def test_command_line(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install . -g CMakeToolchain -g MesonToolchain "
                   "-g MakeToolchain -g MSBuildToolchain")
        self._check(client)
