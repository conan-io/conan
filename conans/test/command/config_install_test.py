import unittest

from conans.test.utils.tools import TestClient, TestBufferConanOutput
import os
import zipfile
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save_files, save
from conans.client.remote_registry import RemoteRegistry, Remote
from mock import patch
from conans.client.rest.uploader_downloader import Downloader


win_profile = """[settings]
    os: Windows
"""

linux_profile = """[settings]
    os: Linux
"""

remotes = """myrepo1 https://myrepourl.net False
my-repo-2 https://myrepo2.com True
"""

registry = """myrepo1 https://myrepourl.net False

Pkg/1.0@user/channel myrepo1
"""

settings_yml = """os:
    Windows:
    Linux:
arch: [x86, x86_64]
"""


def zipdir(path, zipfilename):
    with zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(path):
            for f in files:
                z.write(os.path.join(root, f))


class ConfigInstallTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        registry_path = self.client.client_cache.registry

        save(registry_path, """my-repo-2 https://myrepo2.com True
conan-center https://conan-center.com

MyPkg/0.1@user/channel my-repo-2
Other/1.2@user/channel conan-center
""")
        save(os.path.join(self.client.client_cache.profiles_path, "default"), "#default profile empty")
        save(os.path.join(self.client.client_cache.profiles_path, "linux"), "#empty linux profile")

    def _create_zip(self, zippath=None):
        folder = temp_folder()
        save_files(folder, {"settings.yml": settings_yml,
                            "remotes.txt": remotes,
                            "profiles/linux": linux_profile,
                            "profiles/windows": win_profile})
        zippath = zippath or os.path.join(folder, "myconfig.zip")
        zipdir(folder, zippath)
        return zippath

    def _check(self):
        settings_path = self.client.client_cache.settings_path
        self.assertEqual(load(settings_path), settings_yml)
        registry_path = self.client.client_cache.registry
        registry = RemoteRegistry(registry_path, TestBufferConanOutput())
        self.assertEqual(registry.remotes,
                         [Remote("myrepo1", "https://myrepourl.net", False),
                          Remote("my-repo-2", "https://myrepo2.com", True),
                          ])
        self.assertEqual(registry.refs, {"MyPkg/0.1@user/channel": "my-repo-2"})
        self.assertEqual(sorted(os.listdir(self.client.client_cache.profiles_path)),
                         sorted(["default", "linux", "windows"]))
        self.assertEqual(load(os.path.join(self.client.client_cache.profiles_path, "linux")),
                         linux_profile)
        self.assertEqual(load(os.path.join(self.client.client_cache.profiles_path, "windows")),
                         win_profile)

    def install_file_test(self):
        """ should install from a file in current dir
        """
        zippath = self._create_zip()
        self.client.run('config install "%s"' % zippath)
        self._check()

    def install_url_test(self):
        """ should install from a URL
        """

        def my_download(obj, url, filename, **kwargs):  # @UnusedVariable
            self._create_zip(filename)

        with patch.object(Downloader, 'download', new=my_download):
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check()

            # repeat the process to check
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check()

    def reinstall_test(self):
        """ should use configured URL in conan.conf
        """
        # self.client.run("config install")

    def install_package_test(self):
        """ installing from conan package
        """
        # self.client.run("config install MyConfig/1.0@user/channel")
