import json
import os
import textwrap
from unittest import mock

import pytest
from bottle import static_file, HTTPError, request

from conans.errors import NotFoundException, ConanException
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save, load, rmdir, mkdir, remove


class TestDownloadCacheBackupSources:
    def test_users_download_cache_summary(self):
        def custom_download(this, url, filepath, *args, **kwargs):
            if url.startswith("http://myback"):
                raise NotFoundException()
            save(filepath, f"Hello, world!")

        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader.download",
                        custom_download):
            client = TestClient(default_server_user=True, light=True)
            tmp_folder = temp_folder()
            client.save_home(
                {"global.conf": f"core.sources:download_cache={tmp_folder}\n"
                                "core.sources:download_urls=['origin', 'http://myback']"})
            sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
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
            assert "http://localhost:5000/myfile.txt" in content["references"]["unknown"]
            assert len(content["references"]["unknown"]) == 1

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
            assert "http://localhost.mirror:5000/myfile.txt" in content["references"]["unknown"]
            assert "http://localhost:5000/myfile.txt" in content["references"]["unknown"]
            assert len(content["references"]["unknown"]) == 2

            # Ensure the cache is working and we didn't break anything by modifying the summary
            client.run("source .")
            assert "Downloading file" not in client.out

            client.run("create .")
            content = json.loads(load(os.path.join(tmp_folder, "s", sha256 + ".json")))
            assert content["references"]["pkg/1.0"] == \
                   ["http://localhost.mirror:5000/myfile.txt"]

            client.run("create . --user=barbarian --channel=stable")
            content = json.loads(load(os.path.join(tmp_folder, "s", sha256 + ".json")))
            assert content["references"]["pkg/1.0@barbarian/stable"] == \
                   ["http://localhost.mirror:5000/myfile.txt"]

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = TestClient(default_server_user=True, light=True)
        self.file_server = TestFileServer()
        self.client.servers["file_server"] = self.file_server
        self.download_cache_folder = temp_folder()

    def test_upload_sources_backup(self):
        http_server_base_folder_backups = os.path.join(self.file_server.store, "backups")
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")
        save(os.path.join(self.file_server.store, "mycompanystorage", "mycompanyfile.txt"),
             "Business stuff")
        save(os.path.join(http_server_base_folder_internet, "duplicated1.txt"), "I am duplicated #1")
        save(os.path.join(self.file_server.store, "mycompanystorage2", "duplicated2.txt"),
             "I am duplicated #2")

        hello_world_sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        mycompanyfile_sha256 = "7f1d5d6ae44eb93061b0e07661bd8cbac95a7c51fa204570bf7e24d877d4a224"
        duplicated1_sha256 = "744aca0436e2e355c285fa926a37997df488544589cec2260fc9db969a3c78df"
        duplicated2_sha256 = "66ba2ba05211da3b0b0cb0a08f18e1d9077e7321c2be27887371ec37fade376d"

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg2(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "{self.file_server.fake_url}/internet/myfile.txt",
                            "myfile.txt",
                             sha256="{hello_world_sha256}")

                    download(self, "{self.file_server.fake_url}/mycompanystorage/mycompanyfile.txt",
                            "mycompanyfile.txt",
                             sha256="{mycompanyfile_sha256}")

                    download(self, ["{self.file_server.fake_url}/mycompanystorage/duplicated1.txt",
                                    "{self.file_server.fake_url}/internet/duplicated1.txt"],
                            "duplicated1.txt",
                            sha256="{duplicated1_sha256}")

                    download(self, ["{self.file_server.fake_url}/internet/duplicated1.txt"],
                            "duplicated1.txt",
                            sha256="{duplicated1_sha256}")

                    download(self, ["{self.file_server.fake_url}/mycompanystorage/duplicated2.txt",
                                    "{self.file_server.fake_url}/mycompanystorage2/duplicated2.txt"],
                            "duplicated2.txt",
                            sha256="{duplicated2_sha256}")

                    download(self, "{self.file_server.fake_url}/mycompanystorage2/duplicated2.txt",
                            "duplicated2.txt",
                            sha256="{duplicated2_sha256}")
            """)

        # Ensure that a None url is only warned about but no exception is thrown,
        # this is possible in CI systems that substitute an env var and fail to give it a value
        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=[None, 'origin', '{self.file_server.fake_url}/backups/']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backups/"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .", assert_error=True)
        assert "Trying to download sources from None backup remote" in self.client.out

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['origin', '{self.file_server.fake_url}/backups/']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backups/\n"
                            f"core.sources:exclude_urls=['{self.file_server.fake_url}/mycompanystorage/', "
                            f"'{self.file_server.fake_url}/mycompanystorage2/']"})
        self.client.run("create .")

        self.client.run("upload * -c -r=default")

        # To test #15501 that it works even with extra files in the local cache
        extra_file_path = os.path.join(self.download_cache_folder, "s", "extrafile")
        save(extra_file_path, "Hello, world!")
        self.client.run("upload * -c -r=default", assert_error=True)
        assert "Missing metadata file for backup source" in self.client.out
        os.unlink(extra_file_path)

        server_contents = os.listdir(http_server_base_folder_backups)
        assert hello_world_sha256 in server_contents
        assert hello_world_sha256 + ".json" in server_contents
        # Its only url is excluded, should not be there
        assert mycompanyfile_sha256 not in server_contents
        assert mycompanyfile_sha256 + ".json" not in server_contents
        # It has an excluded url, but another that is not, it should be there
        assert duplicated1_sha256 in server_contents
        assert duplicated1_sha256 + ".json" in server_contents
        # All its urls are excluded, it shoud not be there
        assert duplicated2_sha256 not in server_contents
        assert duplicated2_sha256 + ".json" not in server_contents

        self.client.run("upload * -c -r=default")
        assert "already in server, skipping upload" in self.client.out

        # Clear de local cache
        rmdir(self.download_cache_folder)
        mkdir(self.download_cache_folder)
        # Everything the same, but try to download from backup first
        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backups/', 'origin']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backups/\n"
                            f"core.sources:exclude_urls=['{self.file_server.fake_url}/mycompanystorage/', '{self.file_server.fake_url}/mycompanystorage2/']"})
        self.client.run("source .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in remote backup" in self.client.out
        assert f"File {self.file_server.fake_url}/mycompanystorage/mycompanyfile.txt not found in {self.file_server.fake_url}/backups/" in self.client.out

        # Ensure defaults backup folder works if it's not set in global.conf
        # (The rest is needed to exercise the rest of the code)
        self.client.save_home(
            {"global.conf": f"core.sources:download_urls=['{self.file_server.fake_url}/backups/', 'origin']\n"
                            f"core.sources:exclude_urls=['{self.file_server.fake_url}/mycompanystorage/', '{self.file_server.fake_url}/mycompanystorage2/']"})
        self.client.run("source .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in remote backup" in self.client.out
        assert f"File {self.file_server.fake_url}/mycompanystorage/mycompanyfile.txt not found in {self.file_server.fake_url}/backups/" in self.client.out

    def test_download_origin_first(self):
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        conanfile = textwrap.dedent(f"""
                    from conan import ConanFile
                    from conan.tools.files import download
                    class Pkg2(ConanFile):
                        name = "pkg"
                        version = "1.0"
                        def source(self):
                            download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                                     sha256="{sha256}")
                    """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['origin', '{self.file_server.fake_url}/backup/']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup/"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .")
        self.client.run("upload * -c -r=default")

        rmdir(self.download_cache_folder)

        self.client.run("source .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in origin" in self.client.out
        self.client.run("source .")
        assert f"Source {self.file_server.fake_url}/internet/myfile.txt retrieved from local download cache" in self.client.out

    def test_download_origin_last(self):
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        conanfile = textwrap.dedent(f"""
                    from conan import ConanFile
                    from conan.tools.files import download
                    class Pkg2(ConanFile):
                        name = "pkg"
                        version = "1.0"
                        def source(self):
                            download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                                     sha256="{sha256}")
                    """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backup', 'origin']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . -vv")
        assert f"WARN: File {self.file_server.fake_url}/internet/myfile.txt not found in {self.file_server.fake_url}/backup/" in self.client.out
        assert f"Downloaded {self.file_server.fake_url}/internet/myfile.txt from {self.file_server.fake_url}/internet/myfile.txt"
        self.client.run("upload * -c -r=default")

        rmdir(self.download_cache_folder)

        self.client.run("source .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in remote backup" in self.client.out
        self.client.run("source .")
        assert f"Source {self.file_server.fake_url}/internet/myfile.txt retrieved from local download cache" in self.client.out

    def test_sources_backup_server_error_500(self):
        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                            sha256="unused")
           """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/internal_error/', "
                            f"'{self.file_server.fake_url}/unused/']\n"})
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .", assert_error=True)
        assert "ConanException: Error 500 downloading file" in self.client.out

    def test_sources_backup_server_not_found(self):
        conanfile = textwrap.dedent(f"""
                   from conan import ConanFile
                   from conan.tools.files import download
                   class Pkg2(ConanFile):
                       name = "pkg"
                       version = "1.0"
                       def source(self):
                           download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                                    sha256="unused")
                   """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.download:retry=0\n"
                            f"core.sources:download_urls=['http://locahost/nothing-here', 'origin']\n"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .", assert_error=True)
        assert "ConanException: Error downloading file" in self.client.out

    def test_upload_sources_backup_creds_needed(self):
        client = TestClient(default_server_user=True, light=True)
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

        client.save_home(
            {"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                            f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader/', 'origin']\n"
                            f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"})

        client.save({"conanfile.py": conanfile})
        client.run("create .", assert_error=True)
        assert f"ConanException: The source backup server 'http://localhost:{http_server.port}" \
               f"/downloader/' needs authentication" in client.out
        content = {"credentials": [
            {"url": f"http://localhost:{http_server.port}", "token": "mytoken"}
        ]}
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))

        client.run("create .")
        assert "CONTENT: Hello, world!" in client.out
        client.run("upload * -c -r=default", assert_error=True)
        assert f"The source backup server 'http://localhost:{http_server.port}" \
               f"/uploader/' needs authentication" in client.out
        content = {"credentials": [
            {"url": f"http://localhost:{http_server.port}", "token": "myuploadtoken"}
        ]}
        # Now use the correct UPLOAD token
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))
        client.run("upload * -c -r=default --force")  # need --force to guarantee cached updated

        server_contents = os.listdir(http_server_base_folder_backups)
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        client.run("upload * -c -r=default")
        assert "already in server, skipping upload" in client.out

        content = {"credentials": [
            {"url": f"http://localhost:{http_server.port}", "token": "mytoken"}
        ]}

        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))
        rmdir(download_cache_folder)

        # Remove the "remote" myfile.txt so if it raises
        # we know it tried to download the original source
        os.remove(os.path.join(http_server_base_folder_internet, "myfile.txt"))

        client.run("source .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup" in client.out
        assert "CONTENT: Hello, world!" in client.out
        client.run("source .")
        assert f"Source http://localhost:{http_server.port}/internet/myfile.txt retrieved from local download cache" in client.out
        assert "CONTENT: Hello, world!" in client.out

    def test_download_sources_multiurl(self):
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")
        http_server_base_folder_backup = os.path.join(self.file_server.store, "backup")
        http_server_base_folder_downloader = os.path.join(self.file_server.store, "downloader")

        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")
        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg2(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                             sha256="{sha256}")
            """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup/\n"
                            f"core.sources:download_urls=['origin', '{self.file_server.fake_url}/downloader/', "
                            f"'{self.file_server.fake_url}/backup/']"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .")
        self.client.run("upload * -c -r=default")
        # We upload files to second backup,
        # to ensure that the first one gets skipped in the list but finds in the second one
        server_contents = os.listdir(http_server_base_folder_backup)
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        rmdir(self.download_cache_folder)
        # Remove the "remote" myfile.txt so if it raises
        # we know it tried to download the original source
        remove(os.path.join(http_server_base_folder_internet, "myfile.txt"))

        self.client.run("source .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in remote backup {self.file_server.fake_url}/backup/" in self.client.out

        # And if the first one has them, prefer it before others in the list
        save(os.path.join(http_server_base_folder_downloader, sha256),
             load(os.path.join(http_server_base_folder_backup, sha256)))
        save(os.path.join(http_server_base_folder_downloader, sha256 + ".json"),
             load(os.path.join(http_server_base_folder_backup, sha256 + ".json")))
        rmdir(self.download_cache_folder)
        self.client.run("source .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in remote backup {self.file_server.fake_url}/downloader/" in self.client.out

    def test_list_urls_miss(self):
        def custom_download(this, url, *args, **kwargs):
            raise NotFoundException()

        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader.download",
                        custom_download):
            client = TestClient(default_server_user=True, light=True)
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

            client.save_home(
                {"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                f"core.sources:download_urls=['origin', 'http://extrafake/']\n"})
            client.save({"conanfile.py": conanfile})
            client.run("source .", assert_error=True)
            assert "WARN: Sources for http://fake/myfile.txt failed in 'origin'" in client.out
            assert "WARN: Checking backups" in client.out
            assert "NotFoundException: File http://fake/myfile.txt " \
                   "not found in ['origin', 'http://extrafake/']" in client.out

    def test_ok_when_origin_breaks_midway_list(self):
        http_server_base_folder_backup2 = os.path.join(self.file_server.store, "backup2")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_backup2, sha256), "Hello, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256 + ".json"), '{"references": {}}')

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "{self.file_server.fake_url}/internal_error/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        self.client.save_home(
            {"global.conf": "tools.files.download:retry=0\n"
                            f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/empty/', "
                            f"'origin', '{self.file_server.fake_url}/backup2/']\n"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .")
        assert f"Sources for {self.file_server.fake_url}/internal_error/myfile.txt found in remote backup {self.file_server.fake_url}/backup2/" in self.client.out

    def test_ok_when_origin_authorization_error(self):
        client = TestClient(default_server_user=True, light=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()

        http_server_base_folder_backup1 = temp_folder()
        http_server_base_folder_backup2 = temp_folder()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_backup2, sha256), "Hello, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256 + ".json"), '{"references": {}}')

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return HTTPError(401, "You Are Not Allowed Here")

        @http_server.server.get("/downloader1/<file>")
        def get_file(file):
            return static_file(file, http_server_base_folder_backup1)

        @http_server.server.put("/downloader1/<file>")
        def put_file(file):
            if file in os.listdir(http_server_base_folder_backup1):
                return HTTPError(401, "You Are Not Allowed Here")
            dest = os.path.join(http_server_base_folder_backup1, file)
            with open(dest, 'wb') as f:
                f.write(request.body.read())

        @http_server.server.get("/downloader2/<file>")
        def get_file_2(file):
            return static_file(file, http_server_base_folder_backup2)

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
        client.save_home({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                          f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader1/', "
                          f"'origin', 'http://localhost:{http_server.port}/downloader2/']\n"
                          f"core.sources:upload_url=http://localhost:{http_server.port}/downloader1/\n"
                          "core.upload:retry=0\ncore.download:retry=0"})

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader2/" in client.out
        # TODO: Check better message with Authentication error message
        assert "failed in 'origin'" in client.out

        # Now try to upload once to the first backup server. It's configured so it has write permissions but no overwrite
        client.run("upload * -c -r=default")
        upload_server_contents = os.listdir(http_server_base_folder_backup1)
        assert sha256 in upload_server_contents
        assert sha256 + ".json" in upload_server_contents

        client.run("remove * -c -r=default")

        client.run("upload * -c -r=default")
        assert f"Could not update summary '{sha256}.json' in backup sources server" in client.out

    def test_ok_when_origin_bad_sha256(self):
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")
        http_server_base_folder_backup2 = os.path.join(self.file_server.store, "backup2")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        # This file's sha is not the one in the line above
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Bye, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256), "Hello, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256 + ".json"), '{"references": {}}')

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backup1/', "
                            f"'origin', '{self.file_server.fake_url}/backup2/']\n"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create .")
        assert f"Sources for {self.file_server.fake_url}/internet/myfile.txt found in remote backup {self.file_server.fake_url}/backup2/" in self.client.out
        assert "sha256 signature failed for" in self.client.out

    def test_export_then_upload_workflow(self):
        mkdir(os.path.join(self.download_cache_folder, "s"))

        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")
        http_server_base_folder_backup = os.path.join(self.file_server.store, "backup")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backup/', 'origin']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup/"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("export .")
        self.client.run("upload * -c -r=default")
        # This used to crash because we were trying to list a missing dir if only exports were made
        assert "[Errno 2] No such file or directory" not in self.client.out
        self.client.run("create .")
        self.client.run("upload * -c -r=default")
        assert sha256 in os.listdir(http_server_base_folder_backup)
        self.client.run("cache clean * -bs")
        backups = os.listdir(os.path.join(self.download_cache_folder, "s"))
        assert len(backups) == 0

    def test_export_then_upload_recipe_only_workflow(self):
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backup/', 'origin']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup/"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("export .")
        exported_rev = self.client.exported_recipe_revision()
        self.client.run("upload * --only-recipe -c -r=default")
        # This second run used to crash because we thought there would be some packages always
        self.client.run("upload * --only-recipe -c -r=default")
        # Ensure we are testing for an already uploaded recipe
        assert f"Recipe 'pkg/1.0#{exported_rev}' already in server, skipping upload" in self.client.out

    def test_source_then_upload_workflow(self):
        mkdir(os.path.join(self.download_cache_folder, "s"))

        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")
        http_server_base_folder_backup = os.path.join(self.file_server.store, "backup")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               def source(self):
                   download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backup/', 'origin']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup/"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("source .")
        self.client.run("cache backup-upload")
        # This used to crash because we were trying to list a missing dir if only exports were made
        assert "[Errno 2] No such file or directory" not in self.client.out
        assert sha256 in os.listdir(http_server_base_folder_backup)

    def test_backup_source_corrupted_download_handling(self):
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               def source(self):
                   download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                            sha256="{sha256}")
           """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}"})

        self.client.save({"conanfile.py": conanfile})
        self.client.run("source .")

        # Now simulate a dirty download, the file is there but the sha256 is wrong
        save(os.path.join(self.download_cache_folder, "s", sha256), "Bye bye, world!")

        # Now try to source again, it should eat it up
        self.client.run("source .")

    @pytest.mark.parametrize("exception", [Exception, ConanException])
    @pytest.mark.parametrize("upload", [True, False])
    def test_backup_source_dirty_download_handle(self, exception, upload):
        def custom_download(this, *args, **kwargs):
            raise exception()

        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
                               from conan import ConanFile
                               from conan.tools.files import download
                               class Pkg2(ConanFile):
                                   def source(self):
                                       download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                                                sha256="{sha256}")
                               """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"tools.files.download:retry=0"})

        self.client.save({"conanfile.py": conanfile})

        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader._download_file",
                        custom_download):
            self.client.run("source .", assert_error=True)
            # The mock does not actually download a file, let's add it for the test
            save(os.path.join(self.download_cache_folder, "s", sha256), "__corrupted download__")
            # Check that the dirty file was not removed.
            # This check should go away once we refactor dirty handling
            assert os.path.exists(os.path.join(self.download_cache_folder, "s", f"{sha256}.dirty"))

        if upload:
            self.client.run("cache backup-upload")
        else:
            self.client.run("source .")
        assert f"{sha256} is dirty, removing it" in self.client.out

    @pytest.mark.skip("Recover when .dirty files are properly handled")
    @pytest.mark.parametrize("exception", [Exception, ConanException])
    def test_backup_source_upload_when_dirty(self, exception):
        def custom_download(this, *args, **kwargs):
            raise exception()

        mkdir(os.path.join(self.download_cache_folder, "s"))
        http_server_base_folder_internet = os.path.join(self.file_server.store, "internet")

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
                   from conan import ConanFile
                   from conan.tools.files import download
                   class Pkg2(ConanFile):
                       def source(self):
                           download(self, "{self.file_server.fake_url}/internet/myfile.txt", "myfile.txt",
                                    sha256="{sha256}")
                   """)

        self.client.save_home(
            {"global.conf": f"core.sources:download_cache={self.download_cache_folder}\n"
                            f"core.sources:download_urls=['{self.file_server.fake_url}/backup/', 'origin']\n"
                            f"core.sources:upload_url={self.file_server.fake_url}/backup/"})

        self.client.save({"conanfile.py": conanfile})
        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader._download_file",
                        custom_download):
            self.client.run("source .", assert_error=True)

        # A .dirty file was created, now try to source again, it should detect the dirty download and re-download it
        self.client.run("export . --name=pkg2 --version=1.0")
        self.client.run("upload * -c -r=default")
        assert "No backup sources files to upload" in self.client.out
        assert sha256 + ".dirty" not in os.listdir(os.path.join(self.download_cache_folder, "s"))
