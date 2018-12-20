# coding=utf-8

import os
import textwrap
import unittest
from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient, TestServer


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


class EmptyCacheTestMixin(object):
    """ Will check that the cache after using the link is empty """
    def setUp(self):
        self.servers = {"default": TestServer()}
        self.t = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]},
                            path_with_spaces=False)
        self.reference = ConanFileReference.loads('lib/version@user/channel')
        self.assertFalse(os.path.exists(self.t.client_cache.conan(self.reference)))

    def tearDown(self):
        self.t.run('link {} --remove'.format(self.reference))
        self.assertFalse(self.t.client_cache.installed_as_editable(self.reference))
        self.assertFalse(os.listdir(self.t.client_cache.conan(self.reference)))


class ExistingCacheTestMixin(object):
    """ Will check that the cache after using the link contains the same data as before """
    def setUp(self):
        self.servers = {"default": TestServer()}
        self.t = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]},
                            path_with_spaces=False)
        self.reference = ConanFileReference.loads('lib/version@user/channel')
        self.t.save(files={'conanfile.py': conanfile})
        self.t.run('create . {}'.format(self.reference))
        self.assertTrue(os.path.exists(self.t.client_cache.conan(self.reference)))
        self.assertListEqual(sorted(os.listdir(self.t.client_cache.conan(self.reference))),
                             ['build', 'export', 'export_source', 'locks', 'metadata.json',
                              'package', 'source'])

    def tearDown(self):
        self.t.run('link {} --remove'.format(self.reference))
        self.assertTrue(os.path.exists(self.t.client_cache.conan(self.reference)))
        self.assertListEqual(sorted(os.listdir(self.t.client_cache.conan(self.reference))),
                             ['build', 'export', 'export_source', 'locks', 'metadata.json',
                              'package', 'source'])


class RelatedToGraphBehavior(object):

    def test_do_nothing(self):
        self.t.save(files={'conanfile.py': conanfile,
                           CONAN_PACKAGE_LAYOUT_FILE: conan_package_layout, })
        self.t.run('link . {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

    @parameterized.expand([(True, ), (False, )])
    def test_install_requirements(self, update):
        # Create a parent and remove it from cache
        ref_parent = ConanFileReference.loads("parent/version@lasote/channel")
        self.t.save(files={'conanfile.py': conanfile})
        self.t.run('create . {}'.format(ref_parent))
        self.t.run('upload {} --all'.format(ref_parent))
        self.t.run('remove {} --force'.format(ref_parent))
        self.assertFalse(os.path.exists(self.t.client_cache.conan(ref_parent)))

        # Create our project and link it
        self.t.save(files={'conanfile.py':
                              conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                           CONAN_PACKAGE_LAYOUT_FILE: conan_package_layout, })
        self.t.run('link . {}'.format(self.reference))

        # Install our project and check that everything is in place
        if not update:
            self.t.run('install {}'.format(self.reference))
            self.assertIn("    lib/version@user/channel from local cache - Editable", self.t.out)
            self.assertIn("    parent/version@lasote/channel from 'default' - Downloaded",
                          self.t.out)
            self.assertTrue(os.path.exists(self.t.client_cache.conan(ref_parent)))
        else:
            self.t.run('install {} --update'.format(self.reference), assert_error=True)
            self.assertIn("ERROR: Operation not allowed on a package installed as editable",
                          self.t.out)

    @parameterized.expand([(True,), (False,)])
    def test_middle_graph(self, update):
        # Create a parent and remove it from cache
        ref_parent = ConanFileReference.loads("parent/version@lasote/channel")
        self.t.save(files={'conanfile.py': conanfile})
        self.t.run('create . {}'.format(ref_parent))
        self.t.run('upload {} --all'.format(ref_parent))
        self.t.run('remove {} --force'.format(ref_parent))
        self.assertFalse(os.path.exists(self.t.client_cache.conan(ref_parent)))

        # Create our project and link it
        path_to_lib = os.path.join(self.t.current_folder, 'lib')
        self.t.save(files={'conanfile.py':
                               conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                           CONAN_PACKAGE_LAYOUT_FILE: conan_package_layout, },
                    path=path_to_lib)
        self.t.run('link "{}" {}'.format(path_to_lib, self.reference))

        # Create a child an install it (in other folder, do not override the link!)
        path_to_child = os.path.join(self.t.current_folder, 'child')
        ref_child = ConanFileReference.loads("child/version@lasote/channel")
        self.t.save(files={'conanfile.py': conanfile_base.
                    format(body='requires = "{}"'.format(self.reference)), },
                    path=path_to_child)
        if not update:
            self.t.run('create "{}" {}'.format(path_to_child, ref_child))
            self.assertIn("    child/version@lasote/channel from local cache - Cache", self.t.out)
            self.assertIn("    lib/version@user/channel from local cache - Editable", self.t.out)
            self.assertIn("    parent/version@lasote/channel from 'default' - Downloaded", self.t.out)
            self.assertTrue(os.path.exists(self.t.client_cache.conan(ref_parent)))
        else:
            self.t.run('create "{}" {} --update'.format(path_to_child, ref_child), assert_error=True)
            self.assertIn("ERROR: Operation not allowed on a package installed as editable",
                          self.t.out)


class CreateLinkOverEmptyCache(EmptyCacheTestMixin, RelatedToGraphBehavior, unittest.TestCase):
    pass


class CreateLinkOverExistingCache(ExistingCacheTestMixin, RelatedToGraphBehavior, unittest.TestCase):
    pass
