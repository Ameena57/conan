import unittest
from conans.test.tools import TestClient, TestServer
from conans.util.files import load, save_files
import os
from conans.model.ref import PackageReference, ConanFileReference
import platform

base = '''
from conans import ConanFile
from conans.util.files import load, save
import os

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True

    def source(self):
        extra_path = "1/" * 108
        os.makedirs(extra_path)
        myfile = os.path.join(extra_path, "myfile.txt")
        # print("File length ", len(myfile))
        save(myfile, "Hello extra path length")

    def build(self):
        extra_path = "1/" * 108
        myfile = os.path.join(extra_path, "myfile2.txt")
        # print("File length ", len(myfile))
        save(myfile, "Hello2 extra path length")

    def package(self):
        self.copy("*.txt", keep_path=False)
'''


class PathLengthLimitTest(unittest.TestCase):

    def upload_test(self):
        test_server = TestServer([],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export lasote/channel")
        client.run("install lib/0.1@lasote/channel --build")
        client.run("upload lib/0.1@lasote/channel --all")
        client.run("remove lib/0.1@lasote/channel -f")
        client.run("search")
        self.assertIn("There are no packages", client.user_io.out)

        for download in ("", "--all"):
            client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
            client2.run("install lib/0.1@lasote/channel %s" % download)
            reference = ConanFileReference.loads("lib/0.1@lasote/channel")
            export_folder = client2.client_cache.export(reference)
            export_files = os.listdir(export_folder)
            self.assertNotIn('conan_export.tgz', export_files)
            package_ref = PackageReference.loads("lib/0.1@lasote/channel:"
                                                 "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
            package_folder = client2.client_cache.package(package_ref, short_paths=None)
            if platform.system() == "Windows":
                original_folder = client2.client_cache.package(package_ref)
                link = load(os.path.join(original_folder, ".conan_link"))
                self.assertEqual(link, package_folder)

            files = os.listdir(package_folder)
            self.assertIn("myfile.txt", files)
            self.assertIn("myfile2.txt", files)
            self.assertNotIn("conan_package.tgz", files)

    def basic_test(self):
        client = TestClient()
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export user/channel")
        client.run("install lib/0.1@user/channel --build")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello extra path length", file1)
        file2 = load(os.path.join(package_folder, "myfile2.txt"))
        self.assertEqual("Hello2 extra path length", file2)

        if platform.system() == "Windows":
            conan_ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.client_cache.source(conan_ref)
            link_source = load(os.path.join(source_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_source))

            build_folder = client.client_cache.build(package_ref)
            link_build = load(os.path.join(build_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_build))

            package_folder = client.client_cache.package(package_ref)
            link_package = load(os.path.join(package_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_package))

            client.run("remove lib* -f")
            self.assertFalse(os.path.exists(link_source))
            self.assertFalse(os.path.exists(link_build))
            self.assertFalse(os.path.exists(link_package))

    def failure_test(self):

        base = '''
from conans import ConanFile
from conans.util.files import load, save
import os

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    exports = "*"
    generators = "cmake"

    def build(self):
        self.output.info("%s/%s" % (self.conanfile_directory, self.name))
        print os.listdir(self.conanfile_directory)
        path = os.path.join(self.conanfile_directory, self.name)
        print "PATH EXISTS ", os.path.exists(path)
        print os.listdir(path)
        path = os.path.join(path, "myfile.txt")
        print "PATH EXISTS ", os.path.exists(path)

    def package(self):
        self.copy("*.txt", keep_path=False)
'''

        client = TestClient()
        files = {"conanfile.py": base,
                 "lib/myfile.txt": "Hello world!"}
        client.save(files)
        client.run("export user/channel")
        client.run("install lib/0.1@user/channel --build")
        print client.paths.store
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)

        client.run("install lib/0.1@user/channel --build")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)

    def dummy_test(self):
        import shutil
        from conans.test.utils.test_files import temp_folder
        src_folder = temp_folder()
        save_files(src_folder, {"%s.txt" % s: "Content: %s" % s for s in range(20)})
        for _ in range(1000):
            build_folder = os.path.join(temp_folder(), "dst")
            shutil.copytree(src_folder, build_folder)
            try:
                os.makedirs(build_folder)
                print "SUCCEEDED in CREATING"
            except:
                pass
