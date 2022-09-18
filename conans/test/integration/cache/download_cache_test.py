import os
import textwrap

from bottle import static_file

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save, set_dirty


class TestDownloadCache:

    def test_download_skip(self):
        """ basic proof that enabling download_cache avoids downloading things again
        """
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")
        client.run("remove * -f")

        # enable cache
        tmp_folder = temp_folder()
        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "Downloading" in client.out

        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "Downloading" not in client.out

        # removing the config downloads things
        client.save({"global.conf": ""}, path=client.cache.cache_folder)
        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "Downloading" in client.out

        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)

        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        assert "Downloading" not in client.out

    def test_dirty_download(self):
        # https://github.com/conan-io/conan/issues/8578
        client = TestClient(default_server_user=True)
        tmp_folder = temp_folder()
        client.save({"global.conf": f"core.download:download_cache={tmp_folder}"},
                    path=client.cache.cache_folder)

        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . --name=pkg --version=0.1")
        client.run("upload * -c -r default")
        client.run("remove * -f")
        client.run("install --requires=pkg/0.1@")

        # Make the cache dirty
        for f in os.listdir(tmp_folder):
            # damage the file
            path = os.path.join(tmp_folder, f)
            if os.path.isfile(path):
                save(path, "broken!")
                set_dirty(path)

        client.run("remove * -f")
        client.run("install --requires=pkg/0.1@")
        assert "Downloading" in client.out

        client.run("remove * -f")
        client.run("install --requires=pkg/0.1@")
        assert "Downloading" not in client.out

    def test_user_downloads_cached_newtools(self):
        http_server = StoppableThreadBottle()
        file_path = os.path.join(temp_folder(), "myfile.txt")
        save(file_path, "some content")

        @http_server.server.get("/myfile.txt")
        def get_file():
            return static_file(os.path.basename(file_path), os.path.dirname(file_path))

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
        self.assertTrue(os.path.exists(local_path))
        self.assertEqual("some content", client.load("myfile.txt"))
        local_path2 = os.path.join(client.current_folder, "myfile2.txt")
        self.assertTrue(os.path.exists(local_path2))
        self.assertEqual("some query", client.load("myfile2.txt"))

        # 2 files cached, plus "locks" folder = 3
        # "locks" folder + 2 files cached + .dirty file from previous failure
        self.assertEqual(4, len(os.listdir(cache_folder)))

        # remove remote file
        os.remove(file_path)
        os.remove(local_path)
        os.remove(local_path2)
        # Will use the cached one
        client.run("source .")
        self.assertTrue(os.path.exists(local_path))
        self.assertTrue(os.path.exists(local_path2))
        self.assertEqual("some content", client.load("myfile.txt"))
        self.assertEqual("some query", client.load("myfile2.txt"))

        # disabling cache will make it fail
        os.remove(local_path)
        os.remove(local_path2)
        save(client.cache.new_config_path, "")
        client.run("source .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in source() method, line 8", client.out)
        self.assertIn("Not found: http://localhost", client.out)
