import os
import tempfile
import textwrap
import unittest

import pytest
import yaml

from conans.client.loader import ConanFileLoader
from conans.util.env import environment_update
from conans.model.recipe_ref import RecipeReference
from conans.paths import DATA_YML
from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.util.files import save_files


class SCMDataToConanDataTestCase(unittest.TestCase):
    ref = RecipeReference.loads("name/version@")

    def test_plain_recipe(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "myurl", "revision": "myrev",
                       "username": "myuser", "password": os.environ.get("SECRET", None),
                       "verify_ssl": False, "shallow": False}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'],
                             {"type": "git", "url": "myurl", "revision": "myrev",
                              "verify_ssl": False, "shallow": False})

        # Check the recipe gets the proper values
        t.run("inspect name/version@ -a scm")
        self.assertIn("password: None", t.out)
        self.assertIn("username: myuser", t.out)
        with environment_update({"SECRET": "42"}):
            t.run("inspect name/version@ -a scm")
            self.assertIn("password: 42", t.out)
            self.assertIn("username: myuser", t.out)

    def test_save_special_chars(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": 'weir"d', "revision": 123,
                       "subfolder": "weir\\"d", "submodule": "don't"}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'], {"type": "git", "url": 'weir"d',
                                                           "revision": 123, "subfolder": "weir\"d",
                                                           "submodule": "don't"})

        # Check the recipe gets the proper values
        t.run("inspect name/version@ -a scm")
        self.assertIn("revision: 123", t.out)
        self.assertIn('subfolder: weir"d', t.out)
        self.assertIn("submodule: don't", t.out)
        self.assertIn("revision: 123", t.out)
        self.assertIn('url: weir"d', t.out)

    @pytest.mark.tool_git
    def test_auto_is_replaced(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
        """)
        t = TestClient()
        commit = t.init_git_repo({'conanfile.py': conanfile})
        t.run_command('git remote add origin https://myrepo.com.git')
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'],
                             {"type": "git", "url": 'https://myrepo.com.git', "revision": commit})

        # Check the recipe gets the proper values
        t.run("inspect name/version@ -a scm")
        self.assertIn("revision: {}".format(commit), t.out)
        self.assertIn("type: git", t.out)
        self.assertIn("url: https://myrepo.com.git", t.out)

    def test_existing_field(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "myurl", "revision": "myrev",
                       "username": "myuser", "password": os.environ.get("SECRET", None),}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile,
                DATA_YML: yaml.safe_dump({'.conan': {'scm_data': {}}}, default_flow_style=False)})

        # It fails with it activated
        t.run("export . --name=name --version=version", assert_error=True)
        self.assertIn("ERROR: Field '.conan' inside 'conandata.yml' file is"
                      " reserved to Conan usage.", t.out)

    @pytest.mark.tool_git
    def test_empty_conandata(self):
        # https://github.com/conan-io/conan/issues/8209
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
            """)
        t = TestClient()
        commit = t.init_git_repo({'conanfile.py': conanfile,
                                  'conandata.yml': ""})
        t.run_command('git remote add origin https://myrepo.com.git')
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'],
                             {"type": "git", "url": 'https://myrepo.com.git', "revision": commit})


class ParseSCMFromConanDataTestCase(unittest.TestCase):
    loader = ConanFileLoader(runner=None)

    def test_parse_data(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
        """)
        conan_data = {
            'something_else': {},
            '.conan': {'scm': {
                'type': 'git',
                'url': 'http://myrepo.com',
                'shallow': False,
                'revision': 'abcdefghijk'
            }}}
        test_folder = tempfile.mkdtemp()
        save_files(test_folder, {'conanfile.py': conanfile,
                                 DATA_YML: yaml.safe_dump(conan_data, default_flow_style=False)})

        conanfile_path = os.path.join(test_folder, 'conanfile.py')
        conanfile, _ = self.loader.load_basic_module(conanfile_path=conanfile_path)
        self.assertDictEqual(conanfile.scm, conan_data['.conan']['scm'])


@pytest.mark.tool_git
def test_auto_can_be_automated():
    # https://github.com/conan-io/conan/issues/8881
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile

        class Recipe(ConanFile):
            scm = {"type": "git",
                   "url": os.getenv("USER_EXTERNAL_URL", "auto"),
                   "revision": os.getenv("USER_EXTERNAL_COMMIT", "auto")}
    """)
    t = TestClient()
    commit = t.init_git_repo({'conanfile.py': conanfile,
                              'conandata.yml': ""})
    t.run_command('git remote add origin https://myrepo.com.git')
    t.run("export . --name=pkg --version=1.0")

    def _check(client):
        # Check exported files
        ref = RecipeReference.loads("pkg/1.0")
        ref_layout = client.get_latest_ref_layout(ref)
        assert load(ref_layout.conanfile()) == conanfile
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        assert conan_data['.conan']['scm'] == {"type": "git",
                                               "url": 'https://myrepo.com.git',
                                               "revision": commit}

    _check(t)

    # Now try from another folder, doing a copy and using the env-vars
    t = TestClient(default_server_user=True)
    t.save({"conanfile.py": conanfile})
    with environment_update({"USER_EXTERNAL_URL": "https://myrepo.com.git",
                             "USER_EXTERNAL_COMMIT": commit}):
        t.run("export . --name=pkg --version=1.0")
    _check(t)

    t.run("upload * -c -r default")
    t.run("remove * -f")
    t.run("install --reference=pkg/1.0@ --build", assert_error=True)
    assert "pkg/1.0: SCM: Getting sources from url: 'https://myrepo.com.git'" in t.out

    with environment_update({"USER_EXTERNAL_URL": "https://other.different.url",
                             "USER_EXTERNAL_COMMIT": "invalid commit"}):
        t.run("install --reference=pkg/1.0@ --build", assert_error=True)
        assert "pkg/1.0: SCM: Getting sources from url: 'https://myrepo.com.git'" in t.out
