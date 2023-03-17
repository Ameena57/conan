import json
import os
import textwrap
from unittest import mock

import pytest
from bottle import static_file, request, HTTPError

from conans.errors import NotFoundException
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save, set_dirty, load, rmdir


class TestDownloadCache:

    def test_download_skip(self):
        """ basic proof that enabling download_cache avoids downloading things again
        """
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")
        client.run("remove * -c")

        # enable cache
        tmp_folder = temp_folder()
        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "Downloading" in client.out

        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1@user/testing")
        # TODO assert "Downloading" not in client.out

        # removing the config downloads things
        client.save({"global.conf": ""}, path=client.cache.cache_folder)
        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "Downloading" in client.out

        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)

        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1@user/testing")
        # TODO assert "Downloading" not in client.out

    def test_dirty_download(self):
        # https://github.com/conan-io/conan/issues/8578
        client = TestClient(default_server_user=True)
        tmp_folder = temp_folder()
        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . --name=pkg --version=0.1")
        client.run("upload * -c -r default")
        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@")

        # Make the cache dirty
        for f in os.listdir(tmp_folder):
            # damage the file
            path = os.path.join(tmp_folder, f)
            if os.path.isfile(path):
                save(path, "broken!")
                set_dirty(path)

        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@")
        assert "Downloading" in client.out

        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@")
        # TODO  assert "Downloading" not in client.out

    def test_user_downloads_cached_newtools(self):
        http_server = StoppableThreadBottle()
        file_path = os.path.join(temp_folder(), "myfile.txt")
        save(file_path, "some content")
        file_path_query = os.path.join(temp_folder(), "myfile2.txt")
        save(file_path_query, "some query")

        @http_server.server.get("/myfile.txt")
        def get_file():
            f = file_path_query if request.query else file_path
            return static_file(os.path.basename(f), os.path.dirname(f))

        http_server.run_server()

        client = TestClient()
        tmp_folder = temp_folder()
        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)
        # badchecksums are not cached
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg(ConanFile):
               def source(self):
                   download(self, "http://localhost:%s/myfile.txt", "myfile.txt", md5="kk")
           """ % http_server.port)
        client.save({"conanfile.py": conanfile})
        client.run("source .", assert_error=True)
        assert "ConanException: md5 signature failed for" in client.out
        assert "Provided signature: kk" in client.out

        # There are 2 things in the cache, the "locks" folder and the .dirty file because failure
        assert 2 == len(os.listdir(tmp_folder))  # Nothing was cached

        # This is the right checksum
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                def source(self):
                    md5 = "9893532233caff98cd083a116b013c0b"
                    md5_2 = "0dc8a17658b1c7cfa23657780742a353"
                    download(self, "http://localhost:{0}/myfile.txt", "myfile.txt", md5=md5)
                    download(self, "http://localhost:{0}/myfile.txt?q=2", "myfile2.txt", md5=md5_2)
            """).format(http_server.port)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        local_path = os.path.join(client.current_folder, "myfile.txt")
        assert os.path.exists(local_path)
        assert "some content" in client.load("myfile.txt")
        local_path2 = os.path.join(client.current_folder, "myfile2.txt")
        assert os.path.exists(local_path2)
        assert "some query" in client.load("myfile2.txt")

        # 2 files cached, plus "locks" folder = 3
        # "locks" folder + 2 files cached + .dirty file from previous failure
        assert 2 == len(os.listdir(tmp_folder))
        assert 3 == len(os.listdir(os.path.join(tmp_folder, "c")))

        # remove remote file
        os.remove(file_path)
        os.remove(local_path)
        os.remove(local_path2)
        # Will use the cached one
        client.run("source .")
        assert os.path.exists(local_path)
        assert os.path.exists(local_path2)
        assert "some content" == client.load("myfile.txt")
        assert "some query" == client.load("myfile2.txt")

        # disabling cache will make it fail
        os.remove(local_path)
        os.remove(local_path2)
        save(client.cache.new_config_path, "")
        client.run("source .", assert_error=True)
        assert "ERROR: conanfile.py: Error in source() method, line 8" in client.out
        assert "Not found: http://localhost" in client.out

    def test_download_relative_error(self):
        """ relative paths are not allowed
        """
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        c.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        c.run("upload * --confirm -r default")
        c.run("remove * -c")

        # enable cache
        c.save({"global.conf": f"core.download:download_cache=mytmp_folder"},
               path=c.cache.cache_folder)
        c.run("install --requires=mypkg/0.1@user/testing", assert_error=True)
        assert 'core.download:download_cache must be an absolute path' in c.out


class TestDownloadCacheBackupSources:
    def test_users_download_cache_summary(self):
        def custom_download(this, url, filepath, **kwargs):
            if url.startswith("http://myback"):
                raise NotFoundException()
            save(filepath, f"Hello, world!")

        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader.download",
                        custom_download):
            client = TestClient(default_server_user=True)
            tmp_folder = temp_folder()
            client.save({"global.conf": f"core.backup_sources:download_cache={tmp_folder}\n"
                                        "core.backup_sources:download_urls=['http://myback']"},
                        path=client.cache.cache_folder)
            sha256 = "d9014c4624844aa5bac314773d6b689ad467fa4e1d1a50a1b8a99d5a95f72ff5"
            conanfile = textwrap.dedent(f"""
                from conan import ConanFile
                from conan.tools.files import download
                class Pkg(ConanFile):
                   def source(self):
                       download(self, "http://localhost:5000/myfile.txt", "myfile.txt",
                                sha256="{sha256}")
                """)
            client.save({"conanfile.py": conanfile})
            client.run("source .")

            assert 2 == len(os.listdir(os.path.join(tmp_folder, "s")))
            content = json.loads(load(os.path.join(tmp_folder, "s", sha256 + ".json")))
            assert "http://localhost:5000/myfile.txt" in content["unknown"]
            assert len(content["unknown"]) == 1

            conanfile = textwrap.dedent(f"""
                from conan import ConanFile
                from conan.tools.files import download
                class Pkg2(ConanFile):
                    name = "pkg"
                    version = "1.0"
                    def source(self):
                        download(self, "http://localhost.mirror:5000/myfile.txt", "myfile.txt",
                                 sha256="{sha256}")
                """)
            client.save({"conanfile.py": conanfile})
            client.run("source .")

            assert 2 == len(os.listdir(os.path.join(tmp_folder, "s")))
            content = json.loads(load(os.path.join(tmp_folder, "s", sha256 + ".json")))
            assert "http://localhost.mirror:5000/myfile.txt" in content["unknown"]
            assert "http://localhost:5000/myfile.txt" in content["unknown"]
            assert len(content["unknown"]) == 2

            # Ensure the cache is working and we didn't break anything by modifying the summary
            client.run("source .")
            assert "Downloading file" not in client.out

            client.run("create .")
            content = json.loads(load(os.path.join(tmp_folder, "s", sha256 + ".json")))
            assert content["pkg/1.0#" + client.exported_recipe_revision()] == \
                   ["http://localhost.mirror:5000/myfile.txt"]

    def test_upload_sources_backup(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()
        http_server_base_folder_backups = temp_folder()
        http_server_base_folder_internet = temp_folder()

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return static_file(file, http_server_base_folder_internet)

        @http_server.server.get("/downloader/<file>")
        def get_file(file):
            return static_file(file, http_server_base_folder_backups)

        @http_server.server.put("/uploader/<file>")
        def put_file(file):
            dest = os.path.join(http_server_base_folder_backups, file)
            with open(dest, 'wb') as f:
                f.write(request.body.read())

        http_server.run_server()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg2(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "http://localhost:{http_server.port}/internet/myfile.txt", "myfile.txt",
                             sha256="{sha256}")
            """)

        client.save({"global.conf": f"core.backup_sources:download_cache={download_cache_folder}\n"
                                    f"core.backup_sources:download_urls=['http://localhost:{http_server.port}/downloader/']\n"
                                    f"core.backup_sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        client.run("upload * -c -r=default")

        server_contents = os.listdir(http_server_base_folder_backups)
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        client.run("upload * -c -r=default")
        assert "already in server, skipping upload" in client.out

        rmdir(download_cache_folder)

        # Remove the "remote" myfile.txt so if it raises
        # we know it tried to download the original source
        os.remove(os.path.join(http_server_base_folder_internet, "myfile.txt"))

        client.run("source .")
        assert f"Sources from http://localhost:{http_server.port}/internet/myfile.txt found in remote backup" in client.out
        client.run("source .")
        assert f"Source http://localhost:{http_server.port}/internet/myfile.txt retrieved from local download cache" in client.out

    def test_sources_backup_server_error_500(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()
        http_server_base_folder_backups = temp_folder()
        http_server_base_folder_internet = temp_folder()

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return static_file(file, http_server_base_folder_internet)

        @http_server.server.get("/downloader/<file>")
        def get_file(file):
            return HTTPError(500, "The server has crashed :( :( :(")

        http_server.run_server()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "http://localhost:{http_server.port}/internet/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        client.save({"global.conf": f"core.backup_sources:download_cache={download_cache_folder}\n"
                                    f"core.backup_sources:download_urls=['http://localhost:{http_server.port}/downloader/', "
                                    f"'http://localhost:{http_server.port}/downloader2/']\n"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .", assert_error=True)
        assert "ConanException: Error 500 downloading file" in client.out

    def test_upload_sources_backup_creds_needed(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()
        http_server_base_folder_backups = temp_folder()
        http_server_base_folder_internet = temp_folder()

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        def valid_auth(token):
            auth = request.headers.get("Authorization")
            if auth == f"Bearer {token}":
                return
            return HTTPError(401, "Authentication required")

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return static_file(file, http_server_base_folder_internet)

        @http_server.server.get("/downloader/<file>")
        def get_file(file):
            ret = valid_auth("mytoken")
            return ret or static_file(file, http_server_base_folder_backups)

        @http_server.server.put("/uploader/<file>")
        def put_file(file):
            ret = valid_auth("myuploadtoken")
            if ret:
                return ret
            dest = os.path.join(http_server_base_folder_backups, file)
            with open(dest, 'wb') as f:
                f.write(request.body.read())

        http_server.run_server()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download, load
            class Pkg2(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "http://localhost:{http_server.port}/internet/myfile.txt", "myfile.txt",
                             sha256="{sha256}")
                    self.output.info(f"CONTENT: {{load(self, 'myfile.txt')}}")
            """)

        client.save({"global.conf": f"core.backup_sources:download_cache={download_cache_folder}\n"
                                    f"core.backup_sources:download_urls=['http://localhost:{http_server.port}/downloader/']\n"
                                    f"core.backup_sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .", assert_error=True)
        assert f"ConanException: The source backup server 'http://localhost:{http_server.port}" \
               f"/downloader/' need authentication" in client.out
        content = {f"http://localhost:{http_server.port}": {"token": "mytoken"}}
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))

        client.run("create .")
        assert "CONTENT: Hello, world!" in client.out
        client.run("upload * -c -r=default", assert_error=True)
        assert f"The source backup server 'http://localhost:{http_server.port}" \
               f"/uploader/' need authentication" in client.out
        content = {f"http://localhost:{http_server.port}": {"token": "myuploadtoken"}}
        # Now use the correct UPLOAD token
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))
        client.run("upload * -c -r=default")

        server_contents = os.listdir(http_server_base_folder_backups)
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        client.run("upload * -c -r=default")
        assert "already in server, skipping upload" in client.out

        content = {f"http://localhost:{http_server.port}": {"token": "mytoken"}}
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))
        rmdir(download_cache_folder)

        # Remove the "remote" myfile.txt so if it raises
        # we know it tried to download the original source
        os.remove(os.path.join(http_server_base_folder_internet, "myfile.txt"))

        client.run("source .")
        assert f"Sources from http://localhost:{http_server.port}/internet/myfile.txt found in remote backup" in client.out
        assert "CONTENT: Hello, world!" in client.out
        client.run("source .")
        assert f"Source http://localhost:{http_server.port}/internet/myfile.txt retrieved from local download cache" in client.out
        assert "CONTENT: Hello, world!" in client.out

    def test_download_sources_multiurl(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()
        http_server_base_folder_internet = temp_folder()
        http_server_base_folder_backup1 = temp_folder()
        http_server_base_folder_backup2 = temp_folder()

        server_folders = {"internet": http_server_base_folder_internet,
                          "backup1": http_server_base_folder_backup1,
                          "backup2": http_server_base_folder_backup2,
                          "upload": http_server_base_folder_backup2}

        save(os.path.join(server_folders["internet"], "myfile.txt"), "Hello, world!")
        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return static_file(file, server_folders["internet"])

        @http_server.server.get("/downloader1/<file>")
        def get_file(file):
            return static_file(file, server_folders["backup1"])

        @http_server.server.get("/downloader2/<file>")
        def get_file(file):
            return static_file(file, server_folders["backup2"])

        # Uploader and backup2 are the same
        @http_server.server.put("/uploader/<file>")
        def put_file(file):
            dest = os.path.join(server_folders["upload"], file)
            with open(dest, 'wb') as f:
                f.write(request.body.read())

        http_server.run_server()

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg2(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "http://localhost:{http_server.port}/internet/myfile.txt", "myfile.txt",
                             sha256="{sha256}")
            """)

        client.save({"global.conf": f"core.backup_sources:download_cache={download_cache_folder}\n"
                                    f"core.backup_sources:upload_url=http://localhost:{http_server.port}/uploader/\n"
                                    f"core.backup_sources:download_urls=['http://localhost:{http_server.port}/downloader1/', 'http://localhost:{http_server.port}/downloader2/']"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        client.run("upload * -c -r=default")
        # We upload files to second backup,
        # to ensure that the first one gets skipped in the list but finds in the second one
        server_contents = os.listdir(server_folders["upload"])
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        rmdir(download_cache_folder)
        # Remove the "remote" myfile.txt so if it raises
        # we know it tried to download the original source
        os.remove(os.path.join(server_folders["internet"], "myfile.txt"))

        client.run("source .")
        assert f"Sources from http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader2/" in client.out

        # And if the first one has them, prefer it before others in the list
        server_folders["backup1"] = server_folders["backup2"]
        rmdir(download_cache_folder)
        client.run("source .")
        assert f"Sources from http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader1/" in client.out

    @pytest.mark.parametrize(["policy", "urls_in", "urls_out"], [
        ["ignore", ["http://fake/myfile.txt", "http://extrafake/315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"], []],
        ["warn", ["http://fake/myfile.txt", "http://extrafake/315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"], []],
        ["error", ["http://extrafake/315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"], ["http://fake/myfile.txt"]],
    ])
    def test_cache_miss_policy(self, policy, urls_in, urls_out):
        visited_urls = []

        def custom_download(this, url, *args, **kwargs):
            visited_urls.append(url)
            raise NotFoundException()

        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader.download",
                        custom_download):
            client = TestClient(default_server_user=True)
            download_cache_folder = temp_folder()

            sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"

            conanfile = textwrap.dedent(f"""
                from conan import ConanFile
                from conan.tools.files import download
                class Pkg2(ConanFile):
                    name = "pkg"
                    version = "1.0"
                    def source(self):
                        download(self, "http://fake/myfile.txt", "myfile.txt", sha256="{sha256}")
                """)

            client.save({"global.conf": f"core.backup_sources:download_cache={download_cache_folder}\n"
                                        f"core.backup_sources:download_urls=['http://extrafake/']\n"
                                        f"core.backup_sources:cache_miss_policy={policy}"},
                        path=client.cache.cache_folder)
            client.save({"conanfile.py": conanfile})
            client.run("source .", assert_error=True)
            if policy == "warn":
                assert "Sources from http://fake/myfile.txt not found in remote backup sources" in client.out
            for url_in in urls_in:
                assert url_in in visited_urls
            for url_out in urls_out:
                assert url_out not in visited_urls
