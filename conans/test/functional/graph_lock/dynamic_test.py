import json
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockDynamicTest(unittest.TestCase):

    def remove_dep_test(self):
        # Removing a dependency do not modify the graph of the lockfile
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/0.1@")
        client.run("create . LibB/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")
                                                   .with_require_plain("LibB/0.1")})
        client.run("create . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/0.1")})
        client.run("graph lock .")
        lock1 = client.load("conan.lock")
        lock1 = json.loads(lock1)["graph_lock"]["nodes"]
        self.assertEqual(4, len(lock1))
        liba = lock1["2"]
        self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
        self.assertEqual(liba["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(liba["prev"], "83c38d3b4e5f1b8450434436eec31b00")
        libc = lock1["3"]
        self.assertEqual(libc["ref"], "LibB/0.1#f3367e0e7d170aa12abccb175fee5f97")
        libc = lock1["1"]
        self.assertEqual(libc["ref"], "LibC/0.1#3cc68234fe3b976e1cb15c61afdace6d")
        self.assertEqual(libc["requires"], ["2", "3"])

        # Remove one dep in LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")})
        # If the graph is modified, a create should fail
        client.run("create . LibC/0.1@ --lockfile", assert_error=True)
        self.assertIn("'LibC/0.1' locked requirement 'LibB/0.1' not found", client.out)
