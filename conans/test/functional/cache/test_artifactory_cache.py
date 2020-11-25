import unittest

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class ArtifactoryCacheTestCase(unittest.TestCase):
    def test_rt_cache(self):
        client = TestClient(default_server_user=True)
        cache_folder = temp_folder()
        client.run('remote add conan-center https://conan.bintray.com')
        client.run('config set storage.download_cache="%s"' % cache_folder)
        client.run(
            'config set storage.sources_backup="http://admin:password@0.0.0.0:8082/artifactory/conan-sources"')

        client.run('install zlib/1.2.8@ -r conan-center --build=zlib')
        print(client.out)
        self.fail("AAA")

    def test_download_cache(self):
        pass
