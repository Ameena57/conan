# coding=utf-8
import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient


class CreateEditablePackageTest(unittest.TestCase):

    conanfile_base = textwrap.dedent("""\
        from conans import ConanFile
        
        class APck(ConanFile):
            {body}
        """)
    conanfile = conanfile_base.format(body="pass")

    conan_package_layout = textwrap.dedent("""\
        [includedirs]
        src/include
        """)

    def test_install_ok(self):
        reference = ConanFileReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile, CONAN_PACKAGE_LAYOUT_FILE: ""})
        t.run('link . {}'.format(reference))
        self.assertIn("Reference 'lib/version@user/name' linked to directory '", t.out)

    def test_install_wrong_reference(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': textwrap.dedent("""\
            from conans import ConanFile
            
            class Pck(ConanFile):
                name = "lib"
                version = "version"
            """)})
        t.run('export  . {}'.format(reference))
        t.run('link . wrong/version@user/channel', assert_error=True)
        self.assertIn("ERROR: Name and version from reference (wrong/version@user/channel) and "
                      "target conanfile.py (lib/version) must match", t.out)