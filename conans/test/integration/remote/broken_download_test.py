import os
import textwrap
import unittest

from requests.exceptions import ConnectionError

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestRequester, TestServer
from conans.util.files import save


class BrokenDownloadTest(unittest.TestCase):

    def test_basic(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("export . lasote/stable")
        ref = RecipeReference.loads("hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.get_latest_ref_layout(ref).export()))
        client.run("upload hello/0.1@lasote/stable -r default")
        export_folder = client.get_latest_ref_layout(ref).export()
        client.run("remove hello/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(export_folder))

        rev = server.server_store.get_last_revision(ref).revision
        ref.revision = rev
        path = server.test_server.server_store.export(ref)
        tgz = os.path.join(path, "conan_export.tgz")
        save(tgz, "contents")  # dummy content to break it, so the download decompress will fail
        client.run("install hello/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("Error while extracting downloaded file", client.out)
        self.assertFalse(os.path.exists(client.get_latest_ref_layout(ref).export()))

    def test_client_retries(self):
        server = TestServer()
        servers = {"default": server}
        conanfile = textwrap.dedent("""
        from conans import ConanFile

        class ConanFileToolsTest(ConanFile):
            pass
        """)
        client = TestClient(servers=servers, inputs=["admin", "password"])
        client.save({"conanfile.py": conanfile})
        client.run("create . lib/1.0@lasote/stable")
        client.run("upload lib/1.0@lasote/stable -c --all -r default")

        class DownloadFilesBrokenRequester(TestRequester):
            def __init__(self, times_to_fail=1, *args, **kwargs):
                self.times_to_fail = times_to_fail
                super(DownloadFilesBrokenRequester, self).__init__(*args, **kwargs)

            def get(self, url, **kwargs):
                # conaninfo is skipped sometimes from the output, use manifest
                if "conanmanifest.txt" in url and self.times_to_fail > 0:
                    self.times_to_fail = self.times_to_fail - 1
                    raise ConnectionError("Fake connection error exception")
                else:
                    return super(DownloadFilesBrokenRequester, self).get(url, **kwargs)

        def DownloadFilesBrokenRequesterTimesOne(*args, **kwargs):
            return DownloadFilesBrokenRequester(1, *args, **kwargs)
        client = TestClient(servers=servers, inputs=["admin", "password"],
                            requester_class=DownloadFilesBrokenRequesterTimesOne)
        client.run("install lib/1.0@lasote/stable")
        self.assertIn("ERROR: Error downloading file", client.out)
        self.assertIn('Fake connection error exception', client.out)
        self.assertEqual(1, str(client.out).count("Waiting 0 seconds to retry..."))

        client = TestClient(servers=servers, inputs=["admin", "password"],
                            requester_class=DownloadFilesBrokenRequesterTimesOne)
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [general]
                            retry_wait=1
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("install lib/1.0@lasote/stable")
        self.assertEqual(1, str(client.out).count("Waiting 1 seconds to retry..."))

        def DownloadFilesBrokenRequesterTimesTen(*args, **kwargs):
            return DownloadFilesBrokenRequester(10, *args, **kwargs)
        client = TestClient(servers=servers, inputs=["admin", "password"],
                            requester_class=DownloadFilesBrokenRequesterTimesTen)
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [general]
                            retry=11
                            retry_wait=0
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("install lib/1.0@lasote/stable")
        self.assertEqual(10, str(client.out).count("Waiting 0 seconds to retry..."))
