import os
import textwrap
import unittest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save, set_dirty


class DownloadCacheTest(unittest.TestCase):

    def test_download_skip(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    copy(self, "*", self.source_folder, self.package_folder)
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")
        cache_folder = temp_folder()
        #client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        # TODO: Verify it doesn't really download

        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        # TODO: Verify it doesn't really download

        # removing the config downloads things
        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        # TODO: Verify it doesn't really download
        # restoring config cache works again
        # client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("remove * -f")
        client.run("install --requires=mypkg/0.1@user/testing")
        # TODO: Verify it doesn't really download

    def test_dirty_download(self):
        # https://github.com/conan-io/conan/issues/8578
        client = TestClient(default_server_user=True)
        cache_folder = temp_folder()

        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . --name=pkg --version=0.1")
        client.run("upload * -c -r default")
        client.run("remove * -f")
        client.run("install --requires=pkg/0.1@")
        for f in os.listdir(cache_folder):
            # damage the file
            path = os.path.join(cache_folder, f)
            if os.path.isfile(path):
                save(path, "broken!")
                set_dirty(path)

        client.run("remove * -f")
        client.run("install --requires=pkg/0.1@")
        assert "pkg/0.1: Downloaded package" in client.out

    def test_revision0_v2_skip(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy, load
            class Pkg(ConanFile):
                exports_sources = "*"
                def package(self):
                    copy(self, "*", self.source_folder, self.package_folder)
                def package_info(self):
                    content = load(self, os.path.join(self.package_folder, "header.h"))
                    self.output.warning("CONTENT=>{}#".format(content))
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")

        client2 = TestClient(servers=client.servers)
        cache_folder = temp_folder()

        conan_conf = textwrap.dedent("""
            [storage]
            path = ./data
            download_cache = {}
            [log]
            """.format(cache_folder))
        client2.save({"conan.conf": conan_conf}, path=client2.cache.cache_folder)

        client2.run("install --requires=mypkg/0.1@user/testing")

        def get_value_from_output(output):
            tmp = str(output).split("CONTENT=>")[1]
            return tmp.split("#")[0]

        self.assertEqual("header", get_value_from_output(client2.out))

        # modify non-revisioned pkg
        client.save({"conanfile.py": conanfile,
                     "header.h": "header2"})

        client.run("create . --name=mypkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")

        client2.run("remove * -f")
        client2.run("install --requires=mypkg/0.1@user/testing")

        self.assertEqual("header2", get_value_from_output(client2.out))
