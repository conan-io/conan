import json
import os
import textwrap
from unittest import mock
from bottle import static_file, request, HTTPError
from conans.test.assets.genconanfile import GenConanfile
from conans.errors import NotFoundException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save, load, rmdir


class TestDownloadCacheBackupSources:
    def test_users_download_cache_summary(self):
        def custom_download(this, url, filepath, *args, **kwargs):
            if url.startswith("http://myback"):
                raise NotFoundException()
            save(filepath, f"Hello, world!")

        with mock.patch("conans.client.downloaders.file_downloader.FileDownloader.download",
                        custom_download):
            client = TestClient(default_server_user=True)
            tmp_folder = temp_folder()
            client.save({"global.conf": f"core.sources:download_cache={tmp_folder}\n"
                                        "core.sources:download_urls=['origin', 'http://myback']"},
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=[None, 'origin', 'http://localhost:{http_server.port}/downloader/']\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .", assert_error=True)
        assert "Trying to download sources from None backup remote" in client.out

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['origin', 'http://localhost:{http_server.port}/downloader/']\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)
        client.run("create .")
        client.run("upload * -c -r=default")

        server_contents = os.listdir(http_server_base_folder_backups)
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        client.run("upload * -c -r=default")
        assert "already in server, skipping upload" in client.out

        client.run("source .")
        assert f"Source http://localhost:{http_server.port}/internet/myfile.txt retrieved from local download cache" in client.out

    def test_download_origin_first(self):
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['origin', 'http://localhost:{http_server.port}/downloader/']\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        client.run("upload * -c -r=default")

        rmdir(download_cache_folder)

        client.run("source .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in origin" in client.out
        client.run("source .")
        assert f"Source http://localhost:{http_server.port}/internet/myfile.txt retrieved from local download cache" in client.out

    def test_download_origin_last(self):
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader/', 'origin']\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        client.run("upload * -c -r=default")

        rmdir(download_cache_folder)

        client.run("source .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup" in client.out
        client.run("source .")
        assert f"Source http://localhost:{http_server.port}/internet/myfile.txt retrieved from local download cache" in client.out

    def test_sources_backup_server_error_500(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader/', "
                                    f"'http://localhost:{http_server.port}/downloader2/']\n"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .", assert_error=True)
        assert "ConanException: Error 500 downloading file " in client.out

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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader/', 'origin']\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .", assert_error=True)
        assert f"ConanException: The source backup server 'http://localhost:{http_server.port}" \
               f"/downloader/' needs authentication" in client.out
        content = {"credentials":
                   [{"url": f"http://localhost:{http_server.port}", "token": "mytoken"}]}
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))

        client.run("create .")
        assert "CONTENT: Hello, world!" in client.out
        client.run("upload * -c -r=default", assert_error=True)
        assert f"The source backup server 'http://localhost:{http_server.port}" \
               f"/uploader/' needs authentication" in client.out
        content = {"credentials":
                   [{"url": f"http://localhost:{http_server.port}", "token": "myuploadtoken"}]}
        # Now use the correct UPLOAD token
        save(os.path.join(client.cache_folder, "source_credentials.json"), json.dumps(content))
        client.run("upload * -c -r=default --force")  # need --force to guarantee cached updated

        server_contents = os.listdir(http_server_base_folder_backups)
        assert sha256 in server_contents
        assert sha256 + ".json" in server_contents

        client.run("upload * -c -r=default")
        assert "already in server, skipping upload" in client.out

        content = {"credentials":
                   [{"url": f"http://localhost:{http_server.port}", "token": "mytoken"}]}

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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/\n"
                                    f"core.sources:download_urls=['origin', 'http://localhost:{http_server.port}/downloader1/', 'http://localhost:{http_server.port}/downloader2/']"},
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
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader2/" in client.out

        # And if the first one has them, prefer it before others in the list
        server_folders["backup1"] = server_folders["backup2"]
        rmdir(download_cache_folder)
        client.run("source .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader1/" in client.out

    def test_list_urls_miss(self):
        def custom_download(this, url, *args, **kwargs):
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

            client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                        f"core.sources:download_urls=['origin', 'http://extrafake/']\n"},
                        path=client.cache.cache_folder)
            client.save({"conanfile.py": conanfile})
            client.run("source .", assert_error=True)
            assert "WARN: Sources for http://fake/myfile.txt failed in 'origin'" in client.out
            assert "WARN: Checking backups" in client.out
            assert "NotFoundException: File http://fake/myfile.txt not found " \
                   "in ['origin', 'http://extrafake/']" in client.out

    def test_ok_when_origin_breaks_midway_list(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()

        http_server_base_folder_backup1 = temp_folder()
        http_server_base_folder_backup2 = temp_folder()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_backup2, sha256), "Hello, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256 + ".json"), '{"references": {}}')

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return HTTPError(500, "The server has crashed :( :( :(")

        @http_server.server.get("/downloader1/<file>")
        def get_file(file):
            return static_file(file, http_server_base_folder_backup1)

        @http_server.server.get("/downloader2/<file>")
        def get_file(file):
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader1/', "
                                    f"'origin', 'http://localhost:{http_server.port}/downloader2/']\n"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader2/" in client.out

    def test_ok_when_origin_authorization_error(self):
        client = TestClient(default_server_user=True)
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

        @http_server.server.get("/downloader2/<file>")
        def get_file(file):
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader1/', "
                                    f"'origin', 'http://localhost:{http_server.port}/downloader2/']\n"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader2/" in client.out
        # TODO: Check better message with Authentication error message
        assert "failed in 'origin'" in client.out

    def test_ok_when_origin_bad_sha256(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()

        http_server_base_folder_internet = temp_folder()
        http_server_base_folder_backup1 = temp_folder()
        http_server_base_folder_backup2 = temp_folder()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Bye, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256), "Hello, world!")
        save(os.path.join(http_server_base_folder_backup2, sha256 + ".json"), '{"references": {}}')

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return static_file(file, http_server_base_folder_internet)

        @http_server.server.get("/downloader1/<file>")
        def get_file(file):
            return static_file(file, http_server_base_folder_backup1)

        @http_server.server.get("/downloader2/<file>")
        def get_file(file):
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader1/', "
                                    f"'origin', 'http://localhost:{http_server.port}/downloader2/']\n"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("create .")
        assert f"Sources for http://localhost:{http_server.port}/internet/myfile.txt found in remote backup http://localhost:{http_server.port}/downloader2/" in client.out
        assert "sha256 signature failed for" in client.out

    def test_export_then_upload_workflow(self):
        client = TestClient(default_server_user=True)
        download_cache_folder = temp_folder()
        http_server = StoppableThreadBottle()

        http_server_base_folder_internet = temp_folder()
        http_server_base_folder_backup1 = temp_folder()

        sha256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        save(os.path.join(http_server_base_folder_internet, "myfile.txt"), "Hello, world!")

        @http_server.server.get("/internet/<file>")
        def get_internet_file(file):
            return static_file(file, http_server_base_folder_internet)

        @http_server.server.get("/downloader1/<file>")
        def get_file(file):
            return static_file(file, http_server_base_folder_backup1)

        @http_server.server.put("/uploader/<file>")
        def put_file(file):
            dest = os.path.join(http_server_base_folder_backup1, file)
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

        client.save({"global.conf": f"core.sources:download_cache={download_cache_folder}\n"
                                    f"core.sources:download_urls=['http://localhost:{http_server.port}/downloader1/', 'origin']\n"
                                    f"core.sources:upload_url=http://localhost:{http_server.port}/uploader/"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": conanfile})
        client.run("export .")
        client.run("upload * -c -r=default")
        # This used to crash because we were trying to list a missing dir if only exports were made
        assert "[Errno 2] No such file or directory" not in client.out
        client.run("create .")
        client.run("upload * -c -r=default")
        assert sha256 in os.listdir(http_server_base_folder_backup1)
