# coding=utf-8

import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient


class LinkedPackageAsProject(unittest.TestCase):
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

    def setUp(self):
        self.ref_parent = ConanFileReference.loads("parent/version@user/name")
        self.reference = ConanFileReference.loads('lib/version@user/name')

        self.t = TestClient()
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(self.ref_parent))

        self.t.save(files={'conanfile.py':
                          self.conanfile_base.format(body='requires = "{}"'.format(self.ref_parent)),
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        self.t.run('link . {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))


class InfoCommandOnLocalWorkspaceTest(LinkedPackageAsProject):
    """ Check that commands info/inspect running over an editable package work"""

    def test_no_args(self):
        self.t.run('info .')
        self.assertIn("PROJECT\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n"
                      "parent/version@user/name\n"
                      "    ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.t.out)

    def test_only_none(self):
        self.t.run('info . --only None')
        self.assertIn("PROJECT\n"
                      "parent/version@user/name", self.t.out)

    def test_paths(self):
        self.t.run('info . --paths')
        self.assertIn("PROJECT\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n"
                      "parent/version@user/name\n"
                      "    ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.t.out)


class InfoCommandUsingReferenceTest(LinkedPackageAsProject):

    def test_no_args(self):
        self.t.run('info {}'.format(self.reference))
        self.assertIn("lib/version@user/name\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Remote: None\n"
                      "    Recipe: Editable\n"
                      "    Binary: Editable\n"
                      "    Binary remote: None\n"
                      "    Required by:\n"
                      "        PROJECT\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n"
                      "parent/version@user/name\n"
                      "    ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.t.out)

    def test_only_none(self):
        self.t.run('info {} --only None'.format(self.reference))
        self.assertIn("lib/version@user/name\n"
                      "parent/version@user/name", self.t.out)

    def test_paths(self):
        self.t.run('info {} --paths'.format(self.reference), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)
        # TODO: Cannot show paths for a linked/editable package... what to do here?
