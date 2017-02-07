import unittest
from conans.test.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load, save
from time import sleep


class InstallUpdateTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def update_not_date_test(self):
        # Regression for https://github.com/conan-io/conan/issues/949
        files0 = cpp_hello_conan_files("Hello0", "1.0", build=False)
        files0["conanfile.py"] = files0["conanfile.py"].replace("settings = ", "# settings = ")
        self.client.save(files0)
        self.client.run("export lasote/stable")
        files1 = cpp_hello_conan_files("Hello1", "1.0", build=False,
                                       deps=["Hello0/1.0@lasote/stable"])
        self.client.save(files1, clean_first=True)
        self.client.run("install --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
        package_ref = PackageReference(ref, "55a3af76272ead64e6f543c12ecece30f94d3eda")
        recipe_manifest = self.client.client_cache.digestfile_conanfile(ref)
        package_manifest = self.client.client_cache.digestfile_package(package_ref)
        recipe_timestamp = load(recipe_manifest).splitlines()[0]
        package_timestamp = load(package_manifest).splitlines()[0]

        import time
        time.sleep(1)

        # Change and rebuild package
        files0["helloHello0.h"] = files0["helloHello0.h"] + " // useless comment"
        self.client.save(files0, clean_first=True)
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        new_recipe_timestamp = load(recipe_manifest).splitlines()[0]
        new_package_timestamp = load(package_manifest).splitlines()[0]
        self.assertNotEqual(new_recipe_timestamp, recipe_timestamp)
        self.assertNotEqual(new_package_timestamp, package_timestamp)

        # back to the consumer, try to update
        self.client.save(files1, clean_first=True)
        self.client.run("install --update")
        self.assertIn("ERROR: Current conanfile is newer than default's one",
                      self.client.user_io.out)
        new_recipe_timestamp2 = load(recipe_manifest).splitlines()[0]
        new_package_timestamp2 = load(package_manifest).splitlines()[0]
        self.assertEqual(new_recipe_timestamp, new_recipe_timestamp2)
        self.assertEqual(new_package_timestamp, new_package_timestamp2)

        # hack manifests, put old time
        for manifest_file in (recipe_manifest, package_manifest):
            manifest = load(manifest_file)
            lines = manifest.splitlines()
            lines[0] = "123"
            save(manifest_file, "\n".join(lines))

        self.client.run("install --update")
        new_recipe_timestamp = load(recipe_manifest).splitlines()[0]
        new_package_timestamp = load(package_manifest).splitlines()[0]
        self.assertEqual(new_recipe_timestamp, recipe_timestamp)
        self.assertEqual(new_package_timestamp, package_timestamp)

    def reuse_test(self):
        files = cpp_hello_conan_files("Hello0", "1.0", build=False)

        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client2.run("install Hello0/1.0@lasote/stable")

        files["helloHello0.h"] = "//EMPTY!"
        self.client.save(files, clean_first=True)
        sleep(1)
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        client2.run("install Hello0/1.0@lasote/stable --update")
        ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
        package_ids = client2.paths.conan_packages(ref)
        package_path = client2.paths.package(PackageReference(ref, package_ids[0]))
        header = load(os.path.join(package_path, "include/helloHello0.h"))
        self.assertEqual(header, "//EMPTY!")
