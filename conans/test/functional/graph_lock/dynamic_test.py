import json
import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockDynamicTest(unittest.TestCase):

    def partial_lock_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")})
        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")

        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibC/1.0@ --lockfile=libc.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

        # Two levels
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def partial_multiple_matches_lock_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibA/[>=1.0]")})
        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")

        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibC/1.0@ --lockfile=libc.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

        # Two levels
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def partial_lock_conflict_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibC/1.0@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0 from local", client.out)

        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)

    def partial_lock_root_unused_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})

        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock", assert_error=True)
        self.assertIn("ERROR: The provided lockfile was not used, there is no overlap.", client.out)

    def remove_dep_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/0.1@")
        client.run("create . LibB/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/0.1")
                                                   .with_require("LibB/0.1")})
        client.run("create . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("LibC/0.1")})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        lock = client.load("conan.lock")
        lock = json.loads(lock)["graph_lock"]["nodes"]
        self.assertEqual(4, len(lock))
        libc = lock["1"]
        liba = lock["2"]
        libb = lock["3"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libb["ref"], "LibB/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libc["ref"], "LibC/0.1#3cc68234fe3b976e1cb15c61afdace6d")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libb["ref"], "LibB/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2", "3"])

        # Remove one dep (LibB) in LibC, will fail to create
        client.save({"conanfile.py": GenConanfile().with_require("LibA/0.1")})
        # If the graph is modified, a create should fail
        client.run("create . LibC/0.1@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("Attempt to modify locked LibC/0.1", client.out)

        # It is possible to obtain a new lockfile
        client.run("export . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("LibC/0.1")})
        client.run("lock create conanfile.py --lockfile-out=new.lock")
        # And use the lockfile to build it
        client.run("install LibC/0.1@ --build=LibC --lockfile=new.lock")
        client.run("lock clean-modified new.lock")
        new_lock = client.load("new.lock")
        self.assertNotIn("modified", new_lock)
        new_lock_json = json.loads(new_lock)["graph_lock"]["nodes"]
        self.assertEqual(3, len(new_lock_json))
        libc = new_lock_json["1"]
        liba = new_lock_json["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libc["ref"], "LibC/0.1#ec5e114a9ad4f4269bc4a221b26eb47a")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2"])

    def add_dep_test(self):
        # https://github.com/conan-io/conan/issues/5807
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")

        client.save({"conanfile.py": GenConanfile()})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.save({"conanfile.py": GenConanfile().with_require("zlib/1.0")})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: Require 'zlib' cannot be found in lockfile", client.out)

        # Correct way is generate a new lockfile
        client.run("lock create conanfile.py --lockfile-out=new.lock")
        self.assertIn("zlib/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("Generated lockfile", client.out)
        new = client.load("new.lock")
        lock_file_json = json.loads(new)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        zlib = lock_file_json["graph_lock"]["nodes"]["1"]["ref"]
        if client.cache.config.revisions_enabled:
            self.assertEqual("zlib/1.0#f3367e0e7d170aa12abccb175fee5f97", zlib)
        else:
            self.assertEqual("zlib/1.0", zlib)

        # augment the existing one, works only because it is a consumer only, not package
        client.run("lock create conanfile.py --lockfile=conan.lock --lockfile-out=updated.lock")
        updated = client.load("updated.lock")
        self.assertEqual(updated, new)

    def augment_test_package_requires(self):
        # https://github.com/conan-io/conan/issues/6067
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("tool", "0.1")})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile().with_name("dep").with_version("0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass"),
                     "consumer.txt": "[requires]\ndep/0.1\n",
                     "profile": "[build_requires]\ntool/0.1\n"})

        client.run("export .")
        client.run("lock create consumer.txt -pr=profile --build=missing --lockfile-out=conan.lock")
        lock1 = client.load("conan.lock")
        json_lock1 = json.loads(lock1)
        dep = json_lock1["graph_lock"]["nodes"]["1"]
        self.assertEqual(dep["build_requires"], ["2"])
        self.assertEqual(dep["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        if client.cache.config.revisions_enabled:
            self.assertEqual(dep["ref"], "dep/0.1#01b22a14739e1e2d4cd409c45cac6422")
            self.assertEqual(dep.get("prev"), None)
        else:
            self.assertEqual(dep["ref"], "dep/0.1")
            self.assertEqual(dep.get("prev"), None)

        client.run("create . --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build=missing")
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.assertIn("tool/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        lock2 = client.load("conan.lock")
        json_lock2 = json.loads(lock2)
        dep = json_lock2["graph_lock"]["nodes"]["1"]
        self.assertEqual(dep["build_requires"], ["2"])
        self.assertEqual(dep["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        if client.cache.config.revisions_enabled:
            self.assertEqual(dep["ref"], "dep/0.1#01b22a14739e1e2d4cd409c45cac6422")
            self.assertEqual(dep["prev"], "08cd3e7664b886564720123959c05bdf")
        else:
            self.assertEqual(dep["ref"], "dep/0.1")
            self.assertEqual(dep["prev"], "0")


class PartialOptionsTest(unittest.TestCase):
    """
    When an option is locked in an existing lockfile, and we are using that lockfile to
    create a new one, and somehow the option is changed there are 2 options:
    - Allow the non-locked packages to change the value, according to the dependency resolution
      algorithm. That will produce a different package-id that will be detected and raise
      as incompatible to the locked one
    - Force the locked options, that will result in the same package-id. The package attempting
      to change that option, will not have it set, and can fail later (build time, link time)

    This test implements the 2nd approach, let the lockfile define the options values, not the
    package recipes
    """
    def setUp(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        client.save({"conanfile.py": GenConanfile().with_option("myoption", [True, False])})
        client.run("create . LibA/1.0@ -o LibA:myoption=True")
        self.assertIn("LibA/1.0:d2560ba1787c188a1d7fabeb5f8e012ac53301bb - Build", client.out)
        client.run("create . LibA/1.0@ -o LibA:myoption=False")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.client = client

    def partial_lock_option_command_line_test(self):
        # When in command line, the option value is saved in the libb.lock is applied to all
        # graph, overriding LibC.
        client = self.client
        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")})
        client.run("create . LibB/1.0@ -o LibA:myoption=True")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock -o LibA:myoption=True")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", False)})
        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibC/1.0")})
        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0:d2560ba1787c188a1d7fabeb5f8e012ac53301bb - Cache", client.out)
        self.assertIn("LibB/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Cache", client.out)
        self.assertIn("LibC/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Missing", client.out)

        # Order of LibC, LibB doesn't matter
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")
                                                   .with_require("LibB/1.0")})
        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0:d2560ba1787c188a1d7fabeb5f8e012ac53301bb - Cache", client.out)
        self.assertIn("LibB/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Cache", client.out)
        self.assertIn("LibC/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Missing", client.out)

    def partial_lock_option_conanfile_default_test(self):
        client = self.client
        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", True)})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", False)})
        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self._check()

    def partial_lock_option_conanfile_configure_test(self):
        # when it is locked, it is used, even if other packages define it.
        client = self.client
        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", True)})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        libc = textwrap.dedent("""
            from conans import ConanFile
            class LibC(ConanFile):
                requires = "LibA/1.0"
                def configure(self):
                    self.options["LibA"].myoption = False
            """)
        client.save({"conanfile.py": libc})
        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self._check()

    def _check(self):
        client = self.client

        def _validate():
            client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                       "--lockfile-out=libd.lock", assert_error=True)
            expected = ("LibA/1.0: LibC/1.0 tried to change LibA/1.0 option myoption to False\n"
                        "but it was already defined as True")
            self.assertIn(expected, client.out)

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibC/1.0")})
        _validate()

        # Order of LibC, LibB does matter
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")
                                                   .with_require("LibB/1.0")})
        _validate()
