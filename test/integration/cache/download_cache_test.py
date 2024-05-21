import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save, set_dirty


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
        assert "ConanException: md5 signature failed for" in client.out
        assert "Provided signature: kk" in client.out

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
        save(client.cache.new_config_path, "")
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
