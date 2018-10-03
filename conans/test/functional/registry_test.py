import unittest
import os
from conans.test.utils.test_files import temp_folder
from conans.client.remote_registry import RemoteRegistry, migrate_registry_file, dump_registry, \
    default_remotes
from conans.model.ref import ConanFileReference
from conans.errors import ConanException
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.util.files import save


class RegistryTest(unittest.TestCase):

    def retro_compatibility_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, """conan.io https://server.conan.io
""")  # Without SSL parameter
        new_path = os.path.join(temp_folder(), "aux_file.json")
        migrate_registry_file(f, new_path)
        registry = RemoteRegistry(new_path, TestBufferConanOutput())
        self.assertEqual(registry.remotes_list, [("conan.io", "https://server.conan.io", True)])

    def to_json_migration_test(self):
        tmp = temp_folder()
        conf_dir = os.path.join(tmp, ".conan")
        f = os.path.join(conf_dir, "registry.txt")
        save(f, """conan.io https://server.conan.io True

lib/1.0@conan/stable conan.io
other/1.0@lasote/testing conan.io        
""")
        client = TestClient(base_folder=tmp, servers=False)
        new_path = client.client_cache.registry
        registry = RemoteRegistry(new_path, TestBufferConanOutput())
        self.assertEqual(registry.remotes_list, [("conan.io", "https://server.conan.io", True)])
        self.assertEqual(registry.refs, {'lib/1.0@conan/stable': 'conan.io',
                                         'other/1.0@lasote/testing': 'conan.io'})

    def add_remove_update_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, dump_registry(default_remotes, {}))
        registry = RemoteRegistry(f, TestBufferConanOutput())

        # Add
        registry.add("local", "http://localhost:9300")
        self.assertEqual(registry.remotes_list, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True)])
        # Add
        registry.add("new", "new_url", False)
        self.assertEqual(registry.remotes_list, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True),
                                            ("new", "new_url", False)])
        with self.assertRaises(ConanException):
            registry.add("new", "new_url")
        # Update
        registry.update("new", "other_url")
        self.assertEqual(registry.remotes_list, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True),
                                            ("new", "other_url", True)])
        with self.assertRaises(ConanException):
            registry.update("new2", "new_url")

        registry.update("new", "other_url", False)
        self.assertEqual(registry.remotes_list, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True),
                                            ("new", "other_url", False)])

        # Remove
        registry.remove("local")
        self.assertEqual(registry.remotes_list, [("conan-center", "https://conan.bintray.com", True),
                                            ("new", "other_url", False)])
        with self.assertRaises(ConanException):
            registry.remove("new2")

    def refs_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, dump_registry(default_remotes, {}))
        registry = RemoteRegistry(f, TestBufferConanOutput())
        ref = ConanFileReference.loads("MyLib/0.1@lasote/stable")

        remotes = registry.remotes_list
        registry.set_ref(ref, remotes[0].name)
        remote = registry.get_recipe_remote(ref)
        self.assertEqual(remote, remotes[0])

        registry.set_ref(ref, remotes[0].name)
        remote = registry.get_recipe_remote(ref)
        self.assertEqual(remote, remotes[0])

    def insert_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, """
{
 "remotes": [
  {
   "url": "https://server.conan.io", 
   "verify_ssl": true, 
   "name": "conan.io"
  }
 ], 
 "references": {}
}
""")
        registry = RemoteRegistry(f, TestBufferConanOutput())
        registry.add("repo1", "url1", True, insert=0)
        self.assertEqual(registry.remotes_list, [("repo1", "url1", True),
                                            ("conan.io", "https://server.conan.io", True)])
        registry.add("repo2", "url2", True, insert=1)
        self.assertEqual(registry.remotes_list, [("repo1", "url1", True),
                                            ("repo2", "url2", True),
                                            ("conan.io", "https://server.conan.io", True)])
        registry.add("repo3", "url3", True, insert=5)
        self.assertEqual(registry.remotes_list, [("repo1", "url1", True),
                                            ("repo2", "url2", True),
                                            ("conan.io", "https://server.conan.io", True),
                                            ("repo3", "url3", True)])
