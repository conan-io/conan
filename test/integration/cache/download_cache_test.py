import os
import textwrap
from unittest.mock import patch

from conan.errors import ConanException
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, TestRequester
from conan.internal.util.files import save, set_dirty


class NoFileDownloadsRequester(TestRequester):
    """ Fails any attempt to download the contents of an artifact, while still allowing the
    endpoints needed to resolve what to install (revision and file listings).
    An install succeeding with this requester proves every file came from the download cache.
    """
    def get(self, url, **kwargs):
        # ".../revisions/<rev>/files/<path>" downloads contents, ".../files" is only the listing
        if "/files/" in url:
            raise ConanException(f"Tried to download {url} instead of using the download cache")
        return super().get(url, **kwargs)


class TestDownloadCache:

    def test_download_skip(self):
        """ basic proof that enabling download_cache avoids downloading things again
        """
        client = TestClient(default_server_user=True)
        # generate large random package file
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save
            class Pkg(ConanFile):
                def package(self):
                    fileSizeInBytes = 11000000
                    with open(os.path.join(self.package_folder, "data.txt"), 'wb') as fout:
                        fout.write(os.urandom(fileSizeInBytes))
                """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")
        client.run("remove * -c")

        # enable cache
        tmp_folder = temp_folder()
        client.save_home({"global.conf": f"core.download:download_cache={tmp_folder}"})
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "mypkg/0.1@user/testing: Downloading" in client.out

        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "mypkg/0.1@user/testing: Downloading" not in client.out
        assert "conan_package.tgz from download cache, instead of downloading it" in client.out
        # removing the config downloads things
        client.save_home({"global.conf": ""})
        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "mypkg/0.1@user/testing: Downloading" in client.out

        client.save_home({"global.conf": f"core.download:download_cache={tmp_folder}"})

        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "mypkg/0.1@user/testing: Downloading" not in client.out
        assert "conan_package.tgz from download cache, instead of downloading it" in client.out

    def test_dirty_download(self):
        # https://github.com/conan-io/conan/issues/8578
        client = TestClient(default_server_user=True)
        tmp_folder = temp_folder()
        client.save_home({"global.conf": f"core.download:download_cache={tmp_folder}"})

        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . --name=pkg --version=0.1")
        client.run("upload * -c -r default")
        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@")

        # Make the cache dirty
        # The "c" internal folder must exist, it is the actual storage of blobs
        cache_folder = os.path.join(tmp_folder, "c")
        for f in os.listdir(cache_folder):
            # damage the file
            path = os.path.join(cache_folder, f)
            assert os.path.isfile(path)
            save(path, "broken!")
            set_dirty(path)

        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@")
        assert "Downloading" in client.out

        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@")
        # TODO  assert "Downloading" not in client.out

    def test_user_downloads_cached_newtools(self):
        client = TestClient()
        file_server = TestFileServer()
        client.servers["file_server"] = file_server
        save(os.path.join(file_server.store, "myfile.txt"), "some content")
        save(os.path.join(file_server.store, "myfile2.txt"), "some query")
        save(os.path.join(file_server.store, "myfile3.txt"), "some content 3")

        tmp_folder = temp_folder()
        client.save_home({"global.conf": f"core.sources:download_cache={tmp_folder}"})
        # badchecksums are not cached
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg(ConanFile):
               def source(self):
                   download(self, "%s/myfile.txt", "myfile.txt", md5="kk")
           """ % file_server.fake_url)
        client.save({"conanfile.py": conanfile})
        client.run("source .", assert_error=True)
        assert "ConanException: md5 hash failed for" in client.out
        assert "Provided hash: kk" in client.out

        # There are 2 things in the cache, not sha256, no caching
        assert 0 == len(os.listdir(tmp_folder))  # Nothing was cached

        # This is the right checksum
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                def source(self):
                    md5 = "9893532233caff98cd083a116b013c0b"
                    md5_2 = "0dc8a17658b1c7cfa23657780742a353"
                    sha256 = "bcc23055e479c1050455f5bb457088cfae3cbb2783f7579a7df9e33ea9f43429"
                    download(self, "{0}/myfile.txt", "myfile.txt", md5=md5)
                    download(self, "{0}/myfile3.txt", "myfile3.txt", sha256=sha256)
                    download(self, "{0}/myfile.txt?q=myfile2.txt", "myfile2.txt", md5=md5_2)
            """).format(file_server.fake_url)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        assert "some content" in client.load("myfile.txt")
        assert "some query" in client.load("myfile2.txt")
        assert "some content 3" in client.load("myfile3.txt")

        # remove remote and local files
        os.remove(os.path.join(file_server.store, "myfile3.txt"))
        os.remove(os.path.join(client.current_folder, "myfile.txt"))
        os.remove(os.path.join(client.current_folder, "myfile2.txt"))
        os.remove(os.path.join(client.current_folder, "myfile3.txt"))
        # Will use the cached one
        client.run("source .")
        assert "some content" == client.load("myfile.txt")
        assert "some query" == client.load("myfile2.txt")
        assert "some content 3" in client.load("myfile3.txt")

        # disabling cache will make it fail
        client.save_home({"global.conf": ""})
        client.run("source .", assert_error=True)
        assert "ERROR: conanfile.py: Error in source() method, line 10" in client.out
        assert "Not found" in client.out

    def test_download_relative_error(self):
        """ relative paths are not allowed
        """
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        c.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        c.run("upload * --confirm -r default")
        c.run("remove * -c")

        # enable cache
        c.save_home({"global.conf": f"core.download:download_cache=mytmp_folder"})
        c.run("install --requires=mypkg/0.1@user/testing", assert_error=True)
        assert 'core.download:download_cache must be an absolute path' in c.out

    def test_upload_populates_download_cache(self):
        """ uploading with a download cache configured leaves the uploaded files in the cache,
        so a later install can be served entirely from it, without downloading anything
        """
        client = TestClient(default_server_user=True, requester_class=NoFileDownloadsRequester)
        client.save({"conanfile.py": GenConanfile("mypkg", "0.1").with_package_file("f.txt", "c")})
        client.run("create .")

        tmp_folder = temp_folder()
        client.save_home({"global.conf": f"core.download:download_cache={tmp_folder}"})
        client.run("upload * --confirm -r default")
        # conanfile.py + conanmanifest.txt (recipe) and conaninfo.txt + conanmanifest.txt +
        # conan_package.tgz (package): nothing was ever downloaded, only uploaded
        assert len(os.listdir(os.path.join(tmp_folder, "c"))) == 5

        # the requester forbids downloading contents, so this can only work from the cache
        client.run("remove * -c")
        client.run("install --requires=mypkg/0.1")
        # the install really happened, it did not silently resolve to something already in the cache
        assert "mypkg/0.1: Package installed" in client.out

    def test_upload_without_cache_conf_stores_nothing(self):
        """ the opposite of test_upload_populates_download_cache: without
        core.download:download_cache configured, upload must not write a cache anywhere,
        neither in some default/implicit location nor by ever touching DownloadCache at all
        """
        client = TestClient(default_server_user=True, requester_class=NoFileDownloadsRequester)
        client.save({"conanfile.py": GenConanfile("mypkg", "0.1").with_package_file("f.txt", "c")})
        client.run("create .")

        # no core.download:download_cache set at all
        with patch("conan.internal.rest.download_cache.DownloadCache.cache_file") as cache_file:
            client.run("upload * --confirm -r default")
        cache_file.assert_not_called()

        # nothing was cached, so the install has nowhere to get the files from but the server
        client.run("remove * -c")
        client.save_home({"global.conf": "core.download:retry=0"})
        client.run("install --requires=mypkg/0.1", assert_error=True)
        assert "instead of using the download cache" in client.out

    def test_upload_download_cache_skips_metadata(self):
        """ metadata files can be overwritten without a new revision, so they are never served
        from the cache by ConanInternalCacheDownloader: they must not be cached on upload either
        """
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save
            class Pkg(ConanFile):
                def export(self):
                    save(self, os.path.join(self.recipe_metadata_folder, "logs", "build.log"),
                        "log contents!")
                """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=mypkg --version=0.1")

        tmp_folder = temp_folder()
        client.save_home({"global.conf": f"core.download:download_cache={tmp_folder}"})
        client.run("upload * --confirm -r default")

        # metadata/logs/build.log must be excluded, only the 2 recipe + 3 package files are cached
        assert len(os.listdir(os.path.join(tmp_folder, "c"))) == 5

    def test_upload_relative_error(self):
        """ relative paths are not allowed, same as when downloading
        """
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("mypkg", "0.1").with_package_file("f.txt", "c")})
        client.run("create .")

        client.save_home({"global.conf": "core.download:download_cache=mytmp_folder"})
        client.run("upload * --confirm -r default", assert_error=True)
        assert "core.download:download_cache must be an absolute path" in client.out
