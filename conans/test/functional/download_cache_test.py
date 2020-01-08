import os
import textwrap
import time
import unittest
from collections import Counter
from threading import Thread

from bottle import static_file

from conans.client.rest.download_cache import CachedFileDownloader
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import load, save


class DownloadCacheTest(unittest.TestCase):

    def test_download_skip(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . mypkg/0.1@user/testing")
        client.run("upload * --all --confirm")
        cache_folder = temp_folder()
        log_trace_file = os.path.join(temp_folder(), "mylog.txt")
        client.run('config set storage.download_cache="%s"' % cache_folder)
        client.run('config set log.trace_file="%s"' % log_trace_file)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        self.assertEqual(6, content.count('"_action": "DOWNLOAD"'))
        # 6 files cached, plus "locks" folder = 7
        self.assertEqual(7, len(os.listdir(cache_folder)))

        os.remove(log_trace_file)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        self.assertEqual(0, content.count('"_action": "DOWNLOAD"'))
        self.assertIn("DOWNLOADED_RECIPE", content)
        self.assertIn("DOWNLOADED_PACKAGE", content)

        # removing the config downloads things
        client.run('config rm storage.download_cache')
        os.remove(log_trace_file)
        client.run("remove * -f")
        client.run('config set log.trace_file="%s"' % log_trace_file)
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        # Not cached uses 7, because it downloads twice conaninfo.txt
        self.assertEqual(7, content.count('"_action": "DOWNLOAD"'))

        # restoring config cache works again
        os.remove(log_trace_file)
        client.run('config set storage.download_cache="%s"' % cache_folder)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        self.assertEqual(0, content.count('"_action": "DOWNLOAD"'))

    def user_downloads_cached_test(self):
        http_server = StoppableThreadBottle()

        file_path = os.path.join(temp_folder(), "myfile.txt")
        save(file_path, "some content")

        @http_server.server.get("/myfile.txt")
        def get_file():
            return static_file(os.path.basename(file_path), os.path.dirname(file_path))

        http_server.run_server()

        client = TestClient()
        cache_folder = temp_folder()
        client.run('config set storage.download_cache="%s"' % cache_folder)
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools
            class Pkg(ConanFile):
                def source(self):
                    tools.download("http://localhost:%s/myfile.txt", "myfile.txt",
                                   md5="9893532233caff98cd083a116b013c0b")
            """ % http_server.port)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        local_path = os.path.join(client.current_folder, "myfile.txt")
        self.assertTrue(os.path.exists(local_path))
        self.assertEqual("some content", client.load("myfile.txt"))
        # 1 files cached, plus "locks" folder = 2
        self.assertEqual(2, len(os.listdir(cache_folder)))

        # remove remote file
        os.remove(file_path)
        os.remove(local_path)
        self.assertFalse(os.path.exists(local_path))
        # Will use the cached one
        client.run("source .")
        self.assertTrue(os.path.exists(local_path))
        self.assertEqual("some content", client.load("myfile.txt"))

        # disabling cache will make it fail
        os.remove(local_path)
        client.run("config rm storage.download_cache")
        client.run("source .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in source() method, line 6", client.out)
        self.assertIn("Not found: http://localhost", client.out)


class CachedDownloaderUnitTest(unittest.TestCase):
    def setUp(self):
        cache_folder = temp_folder()

        class FakeFileDownloader(object):
            def __init__(self):
                self.calls = Counter()

            def download(self, url, file_path_=None, *args, **kwargs):
                if "slow" in url:
                    time.sleep(0.5)
                self.calls[url] += 1
                if file_path_:
                    save(file_path_, url)
                else:
                    return url

        self.file_downloader = FakeFileDownloader()
        self.cached_downloader = CachedFileDownloader(cache_folder, self.file_downloader)

    def concurrent_locks_test(self):
        folder = temp_folder()

        def download(index):
            if index % 2:
                content = self.cached_downloader.download("slow_testurl")
            else:
                file_path = os.path.join(folder, "myfile%s.txt" % index)
                self.cached_downloader.download("slow_testurl", file_path)
                content = load(file_path)
            self.assertEqual(content, "slow_testurl")
            self.assertEqual(self.file_downloader.calls["slow_testurl"], 1)

        ps = []
        for i in range(8):
            thread = Thread(target=download, args=(i,))
            thread.start()
            ps.append(thread)

        for p in ps:
            p.join()

        self.assertEqual(self.file_downloader.calls["slow_testurl"], 1)

    def test_basic(self):
        folder = temp_folder()
        file_path = os.path.join(folder, "myfile.txt")
        self.cached_downloader.download("testurl", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        self.assertEqual("testurl", load(file_path))

        # Try again, the count will be the same
        self.cached_downloader.download("testurl", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        # Try direct content
        content = self.cached_downloader.download("testurl")
        self.assertEqual(content.decode("utf-8"), "testurl")
        self.assertEqual(self.file_downloader.calls["testurl"], 1)

        # Try another file
        file_path = os.path.join(folder, "myfile2.txt")
        self.cached_downloader.download("testurl2", file_path)
        self.assertEqual(self.file_downloader.calls["testurl2"], 1)
        self.assertEqual("testurl2", load(file_path))
        self.cached_downloader.download("testurl2", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        self.assertEqual(self.file_downloader.calls["testurl2"], 1)

    def test_content_first(self):
        # first calling content without path also caches
        content = self.cached_downloader.download("testurl")
        self.assertEqual(content.decode("utf-8"), "testurl")  # content is binary here
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        # Now the file
        folder = temp_folder()
        file_path = os.path.join(folder, "myfile.txt")
        self.cached_downloader.download("testurl", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        self.assertEqual("testurl", load(file_path))
