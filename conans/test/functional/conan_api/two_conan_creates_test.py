import os
import unittest
import platform

from conans.client.conan_api import ConanAPIV1
from conans.client.tools.env import environment_append
from conans.client.tools.files import chdir
from conans.model.ref import PackageReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import load


class ConanCreateTest(unittest.TestCase):

    @unittest.skipUnless(platform.system() == "Windows", "only Windows test")
    def test_preprocessor_called_second_api_call(self):
        """"When calling twice to conan create with the Conan python API, the default settings shouldn't be cached.
        To test that the default profile is not cached, this test is verifying that the setting preprocessor is
        adjusting the runtime to MDd when build_type=Debug after a different call to conan create that could cache
        the runtime to MD (issue reported at: #4246) """
        tmp = temp_folder()
        with environment_append({"CONAN_USER_HOME": tmp}):
            with chdir(tmp):
                api, cache, user_io = ConanAPIV1.factory()
                api.new(name="lib/1.0@conan/stable", bare=True)

                def get_conaninfo(info):
                    package_id = info["installed"][0]["packages"][0]["id"]
                    folder = cache.package(PackageReference.loads("lib/1.0@conan/stable:%s" % package_id))
                    return load(os.path.join(folder, "conaninfo.txt"))

                info = api.create(".", user="conan", channel="stable", settings=["compiler=Visual Studio", "compiler.version=15", "build_type=Release"])
                self.assertIn("compiler.runtime=MD", get_conaninfo(info))
                info = api.create(".", user="conan", channel="stable", settings=["compiler=Visual Studio", "compiler.version=15", "build_type=Debug"])
                self.assertIn("compiler.runtime=MDd", get_conaninfo(info))
