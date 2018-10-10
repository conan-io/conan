import unittest

from conans.test.utils.tools import TestClient, TestBufferConanOutput
import os
import zipfile
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save_files, save, mkdir
from conans.client.remote_registry import RemoteRegistry, Remote
from mock import patch
from conans.client.rest.uploader_downloader import Downloader
from conans import tools
from conans.client.conf import ConanClientConfigParser
from conans.client.conf.config_installer import _hide_password
import shutil


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

conan_conf = """
[log]
run_to_output = False       # environment CONAN_LOG_RUN_TO_OUTPUT
level = 10                  # environment CONAN_LOGGING_LEVEL

[general]
compression_level = 6                 # environment CONAN_COMPRESSION_LEVEL
cpu_count = 1             # environment CONAN_CPU_COUNT

[proxies]
# Empty section will try to use system proxies.
# If don't want proxy at all, remove section [proxies]
# As documented in http://docs.python-requests.org/en/latest/user/advanced/#proxies
http = http://user:pass@10.10.1.10:3128/
no_proxy = mylocalhost
https = None
# http = http://10.10.1.10:3128
# https = http://10.10.1.10:1080
"""

myfuncpy = """def mycooladd(a, b):
    return a + b
"""


def zipdir(path, zipfilename):
    with zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(path):
            for f in files:
                file_path = os.path.join(root, f)
                if file_path == zipfilename:
                    continue
                relpath = os.path.relpath(file_path, path)
                z.write(file_path, relpath)


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

        self.old_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def _create_profile_folder(self, folder=None):
        folder = folder or temp_folder(path_with_spaces=False)
        save_files(folder, {"settings.yml": settings_yml,
                            "remotes.txt": remotes,
                            "profiles/linux": linux_profile,
                            "profiles/windows": win_profile,
                            "config/conan.conf": conan_conf,
                            "pylintrc": "#Custom pylint",
                            "python/myfuncs.py": myfuncpy,
                            "python/__init__.py": ""})
        return folder

    def _create_zip(self, zippath=None):
        folder = self._create_profile_folder()
        zippath = zippath or os.path.join(folder, "myconfig.zip")
        zipdir(folder, zippath)
        return zippath

    def _check(self, install_path):
        settings_path = self.client.client_cache.settings_path
        self.assertEqual(load(settings_path).splitlines(), settings_yml.splitlines())
        registry_path = self.client.client_cache.registry
        registry = RemoteRegistry(registry_path, TestBufferConanOutput())
        self.assertEqual(registry.remotes,
                         [Remote("myrepo1", "https://myrepourl.net", False),
                          Remote("my-repo-2", "https://myrepo2.com", True),
                          ])
        self.assertEqual(registry.refs, {"MyPkg/0.1@user/channel": "my-repo-2"})
        self.assertEqual(sorted(os.listdir(self.client.client_cache.profiles_path)),
                         sorted(["default", "linux", "windows"]))
        self.assertEqual(load(os.path.join(self.client.client_cache.profiles_path, "linux")).splitlines(),
                         linux_profile.splitlines())
        self.assertEqual(load(os.path.join(self.client.client_cache.profiles_path, "windows")).splitlines(),
                         win_profile.splitlines())
        conan_conf = ConanClientConfigParser(self.client.client_cache.conan_conf_path)
        self.assertEqual(conan_conf.get_item("log.run_to_output"), "False")
        self.assertEqual(conan_conf.get_item("log.run_to_file"), "False")
        self.assertEqual(conan_conf.get_item("log.level"), "10")
        self.assertEqual(conan_conf.get_item("general.compression_level"), "6")
        self.assertEqual(conan_conf.get_item("general.sysrequires_sudo"), "True")
        self.assertEqual(conan_conf.get_item("general.cpu_count"), "1")
        self.assertEqual(conan_conf.get_item("general.config_install"), install_path)
        self.assertEqual(conan_conf.get_item("proxies.no_proxy"), "mylocalhost")
        self.assertEqual(conan_conf.get_item("proxies.https"), "None")
        self.assertEqual(conan_conf.get_item("proxies.http"), "http://user:pass@10.10.1.10:3128/")
        self.assertEqual("#Custom pylint",
                         load(os.path.join(self.client.client_cache.conan_folder, "pylintrc")))
        self.assertEqual("",
                         load(os.path.join(self.client.client_cache.conan_folder, "python",
                                           "__init__.py")))

    def reuse_python_test(self):
        zippath = self._create_zip()
        self.client.run('config install "%s"' % zippath)
        conanfile = """from conans import ConanFile
from myfuncs import mycooladd
a = mycooladd(1, 2)
assert a == 3
class Pkg(ConanFile):
    def build(self):
        self.output.info("A is %s" % a)
"""
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . Pkg/0.1@user/testing")
        self.assertIn("A is 3", self.client.out)

    def install_file_test(self):
        """ should install from a file in current dir
        """
        zippath = self._create_zip()
        self.client.run('config install "%s"' % zippath)
        self._check(zippath)
        self.assertTrue(os.path.exists(zippath))

    def install_dir_test(self):
        """ should install from a dir in current dir
        """
        folder = self._create_profile_folder()
        self.assertTrue(os.path.isdir(folder))
        self.client.run('config install "%s"' % folder)
        self._check(folder)

    def test_without_profile_folder(self):
        shutil.rmtree(self.client.client_cache.profiles_path)
        zippath = self._create_zip()
        self.client.run('config install "%s"' % zippath)
        self.assertEqual(sorted(os.listdir(self.client.client_cache.profiles_path)),
                         sorted(["linux", "windows"]))
        self.assertEqual(load(os.path.join(self.client.client_cache.profiles_path, "linux")).splitlines(),
                         linux_profile.splitlines())

    def install_url_test(self):
        """ should install from a URL
        """

        def my_download(obj, url, filename, **kwargs):  # @UnusedVariable
            self._create_zip(filename)

        with patch.object(Downloader, 'download', new=my_download):
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check("http://myfakeurl.com/myconf.zip")

            # repeat the process to check
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check("http://myfakeurl.com/myconf.zip")

    def failed_install_repo_test(self):
        """ should install from a git repo
        """
        error = self.client.run('config install notexistingrepo.git', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: config install error. Can't clone repo", self.client.out)

    def failed_install_http_test(self):
        """ should install from a http zip
        """
        error = self.client.run('config install httpnonexisting', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Error while installing config from httpnonexisting",
                      self.client.out)

    def install_repo_test(self):
        """ should install from a git repo
        """

        folder = self._create_profile_folder()
        with tools.chdir(folder):
            self.client.runner('git init .')
            self.client.runner('git add .')
            self.client.runner('git config user.name myname')
            self.client.runner('git config user.email myname@mycompany.com')
            self.client.runner('git commit -m "mymsg"')

        self.client.run('config install "%s/.git"' % folder)
        self._check("%s/.git" % folder)

    def install_repo_relative_test(self):
        relative_folder = "./config"
        absolute_folder = os.path.join(self.client.current_folder, "config")
        mkdir(absolute_folder)
        folder = self._create_profile_folder(absolute_folder)
        with tools.chdir(folder):
            self.client.runner('git init .')
            self.client.runner('git add .')
            self.client.runner('git config user.name myname')
            self.client.runner('git config user.email myname@mycompany.com')
            self.client.runner('git commit -m "mymsg"')

        self.client.run('config install "%s/.git"' % relative_folder)
        self._check(os.path.join("%s" % folder, ".git"))

    def install_custom_args_test(self):
        """ should install from a git repo
        """

        folder = self._create_profile_folder()
        with tools.chdir(folder):
            self.client.runner('git init .')
            self.client.runner('git add .')
            self.client.runner('git config user.name myname')
            self.client.runner('git config user.email myname@mycompany.com')
            self.client.runner('git commit -m "mymsg"')

        self.client.run('config install "%s/.git" --args="-c init.templateDir=\"\""' % folder)
        self._check("%s/.git" % folder)

    def force_git_type_test(self):
        client = TestClient()
        error = client.run('config install httpnonexisting --type=git', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Can't clone repo", client.out)

    def reinstall_test(self):
        """ should use configured URL in conan.conf
        """
        zippath = self._create_zip()
        self.client.run('config set general.config_install="%s"' % zippath)
        self.client.run("config install")
        self._check(zippath)

    def reinstall_error_test(self):
        """ should use configured URL in conan.conf
        """
        error = self.client.run("config install", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Called config install without arguments", self.client.out)

    def removed_credentials_from_url_unit_test(self):
        """
        Unit tests to remove credentials in netloc from url when using basic auth
        # https://github.com/conan-io/conan/issues/2324
        """
        url_without_credentials = r"https://server.com/resource.zip"
        url_with_credentials = r"https://test_username:test_password_123@server.com/resource.zip"
        url_hidden_password = r"https://test_username:<hidden>@server.com/resource.zip"

        # Check url is the same when not using credentials
        self.assertEqual(_hide_password(url_without_credentials), url_without_credentials)

        # Check password is hidden using url with credentials
        self.assertEqual(_hide_password(url_with_credentials), url_hidden_password)

        # Check that it works with other protocols ftp
        ftp_with_credentials = r"ftp://test_username_ftp:test_password_321@server.com/resurce.zip"
        ftp_hidden_password = r"ftp://test_username_ftp:<hidden>@server.com/resurce.zip"
        self.assertEqual(_hide_password(ftp_with_credentials), ftp_hidden_password)

        # Check function also works for file paths *unix/windows
        unix_file_path = r"/tmp/test"
        self.assertEqual(_hide_password(unix_file_path), unix_file_path)
        windows_file_path = r"c:\windows\test"
        self.assertEqual(_hide_password(windows_file_path), windows_file_path)

        # Check works with empty string
        self.assertEqual(_hide_password(''), '')

    def remove_credentials_config_installer_test(self):
        """ Functional test to check credentials are not displayed in output but are still present
        in conan configuration
        # https://github.com/conan-io/conan/issues/2324
        """
        fake_url_with_credentials = "http://test_user:test_password@myfakeurl.com/myconf.zip"
        fake_url_hidden_password = "http://test_user:<hidden>@myfakeurl.com/myconf.zip"

        def my_download(obj, url, filename, **kwargs):  # @UnusedVariable
            self.assertEqual(url, fake_url_with_credentials)
            self._create_zip(filename)

        with patch.object(Downloader, 'download', new=my_download):
            self.client.run("config install %s" % (fake_url_with_credentials,))

            # Check credentials are not displayed in output
            self.assertNotIn(fake_url_with_credentials, self.client.out)
            self.assertIn(fake_url_hidden_password, self.client.out)

            # Check credentials still stored in configuration
            self._check(fake_url_with_credentials)

    def ssl_verify_test(self):
        fake_url = "https://fakeurl.com/myconf.zip"

        def download_verify_false(obj, url, filename, **kwargs):  # @UnusedVariable
            self.assertFalse(obj.verify)
            self._create_zip(filename)

        def download_verify_true(obj, url, filename, **kwargs):  # @UnusedVariable
            self.assertTrue(obj.verify)
            self._create_zip(filename)

        with patch.object(Downloader, 'download', new=download_verify_false):
            self.client.run("config install %s --verify-ssl=False" % fake_url)

        with patch.object(Downloader, 'download', new=download_verify_true):
            self.client.run("config install %s --verify-ssl=True" % fake_url)
