import json
import os
import shutil
import textwrap
import unittest
import zipfile

import six
from mock import patch

from conans.client.cache.remote_registry import Remote
from conans.client.conf import ConanClientConfigParser
from conans.client.conf.config_installer import _hide_password, _ConfigOrigin
from conans.client.rest.uploader_downloader import FileDownloader
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import load, mkdir, save, save_files


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
default_package_id_mode = full_package_mode # environment CONAN_DEFAULT_PACKAGE_ID_MODE

[proxies]
# Empty section will try to use system proxies.
# If don't want proxy at all, remove section [proxies]
# As documented in http://docs.python-requests.org/en/latest/user/advanced/#proxies
http = http://user:pass@10.10.1.10:3128/
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
        save(os.path.join(self.client.cache.profiles_path, "default"), "#default profile empty")
        save(os.path.join(self.client.cache.profiles_path, "linux"), "#empty linux profile")

    def _create_profile_folder(self, folder=None):
        folder = folder or temp_folder(path_with_spaces=False)
        save_files(folder, {"settings.yml": settings_yml,
                            "remotes.txt": remotes,
                            "profiles/linux": linux_profile,
                            "profiles/windows": win_profile,
                            "hooks/dummy": "#hook dummy",
                            "hooks/foo.py": "#hook foo",
                            "hooks/custom/custom.py": "#hook custom",
                            ".git/hooks/foo": "foo",
                            "hooks/.git/hooks/before_push": "before_push",
                            "config/conan.conf": conan_conf,
                            "pylintrc": "#Custom pylint",
                            "python/myfuncs.py": myfuncpy,
                            "python/__init__.py": ""
                            })
        return folder

    def config_hooks_test(self):
        # Make sure the conan.conf hooks information is appended
        folder = temp_folder(path_with_spaces=False)
        conan_conf = textwrap.dedent("""
            [hooks]
            foo
            custom/custom
            """)
        save_files(folder, {"config/conan.conf": conan_conf})
        client = TestClient()
        client.run('config install "%s"' % folder)
        self.assertIn("Processing conan.conf", client.out)
        content = load(client.cache.conan_conf_path)
        self.assertEqual(1, content.count("foo"))
        self.assertEqual(1, content.count("custom/custom"))

        config = ConanClientConfigParser(client.cache.conan_conf_path)
        hooks = config.get_item("hooks")
        self.assertIn("foo", hooks)
        self.assertIn("custom/custom", hooks)
        self.assertIn("attribute_checker", hooks)
        client.run('config install "%s"' % folder)
        self.assertIn("Processing conan.conf", client.out)
        content = load(client.cache.conan_conf_path)
        self.assertEqual(1, content.count("foo"))
        self.assertEqual(1, content.count("custom/custom"))

    def _create_zip(self, zippath=None):
        folder = self._create_profile_folder()
        zippath = zippath or os.path.join(folder, "myconfig.zip")
        zipdir(folder, zippath)
        return zippath

    def _check(self, params):
        typ, uri, verify, args = [p.strip() for p in params.split(",")]
        configs = json.loads(load(self.client.cache.config_install_file))
        config = _ConfigOrigin(configs[0])
        self.assertEqual(config.type, typ)
        self.assertEqual(config.uri, uri)
        self.assertEqual(str(config.verify_ssl), verify)
        self.assertEqual(str(config.args), args)
        settings_path = self.client.cache.settings_path
        self.assertEqual(load(settings_path).splitlines(), settings_yml.splitlines())
        remotes = self.client.cache.registry.load_remotes()
        self.assertEqual(list(remotes.values()), [Remote("myrepo1", "https://myrepourl.net", False),
                                                  Remote("my-repo-2", "https://myrepo2.com", True),
                                                  ])
        self.assertEqual(sorted(os.listdir(self.client.cache.profiles_path)),
                         sorted(["default", "linux", "windows"]))
        self.assertEqual(load(os.path.join(self.client.cache.profiles_path, "linux")).splitlines(),
                         linux_profile.splitlines())
        self.assertEqual(load(os.path.join(self.client.cache.profiles_path,
                                           "windows")).splitlines(),
                         win_profile.splitlines())
        conan_conf = ConanClientConfigParser(self.client.cache.conan_conf_path)
        self.assertEqual(conan_conf.get_item("log.run_to_output"), "False")
        self.assertEqual(conan_conf.get_item("log.run_to_file"), "False")
        self.assertEqual(conan_conf.get_item("log.level"), "10")
        self.assertEqual(conan_conf.get_item("general.compression_level"), "6")
        self.assertEqual(conan_conf.get_item("general.default_package_id_mode"),
                         "full_package_mode")
        self.assertEqual(conan_conf.get_item("general.sysrequires_sudo"), "True")
        self.assertEqual(conan_conf.get_item("general.cpu_count"), "1")
        with six.assertRaisesRegex(self, ConanException, "'config_install' doesn't exist"):
            conan_conf.get_item("general.config_install")
        self.assertEqual(conan_conf.get_item("proxies.https"), "None")
        self.assertEqual(conan_conf.get_item("proxies.http"), "http://user:pass@10.10.1.10:3128/")
        self.assertEqual("#Custom pylint",
                         load(os.path.join(self.client.cache_folder, "pylintrc")))
        self.assertEqual("",
                         load(os.path.join(self.client.cache_folder, "python",
                                           "__init__.py")))
        self.assertEqual("#hook dummy",
                         load(os.path.join(self.client.cache_folder, "hooks", "dummy")))
        self.assertEqual("#hook foo",
                         load(os.path.join(self.client.cache_folder, "hooks", "foo.py")))
        self.assertEqual("#hook custom",
                         load(os.path.join(self.client.cache_folder, "hooks", "custom",
                                           "custom.py")))
        self.assertFalse(os.path.exists(os.path.join(self.client.cache_folder, "hooks",
                                                     ".git")))
        self.assertFalse(os.path.exists(os.path.join(self.client.cache_folder, ".git")))

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
        self._check("file, %s, True, None" % zippath)
        self.assertTrue(os.path.exists(zippath))

    def install_dir_test(self):
        """ should install from a dir in current dir
        """
        folder = self._create_profile_folder()
        self.assertTrue(os.path.isdir(folder))
        self.client.run('config install "%s"' % folder)
        self._check("dir, %s, True, None" % folder)

    def install_source_target_folders_test(self):
        folder = temp_folder()
        save_files(folder, {"subf/file.txt": "hello",
                            "subf/subf/file2.txt": "bye"})
        self.client.run('config install "%s" -sf=subf -tf=newsubf' % folder)
        content = load(os.path.join(self.client.cache_folder, "newsubf/file.txt"))
        self.assertEqual(content, "hello")
        content = load(os.path.join(self.client.cache_folder, "newsubf/subf/file2.txt"))
        self.assertEqual(content, "bye")

    def install_multiple_configs_test(self):
        folder = temp_folder()
        save_files(folder, {"subf/file.txt": "hello",
                            "subf2/file2.txt": "bye"})
        self.client.run('config install "%s" -sf=subf' % folder)
        content = load(os.path.join(self.client.cache_folder, "file.txt"))
        file2 = os.path.join(self.client.cache_folder, "file2.txt")
        self.assertEqual(content, "hello")
        self.assertFalse(os.path.exists(file2))
        self.client.run('config install "%s" -sf=subf2' % folder)
        content = load(file2)
        self.assertEqual(content, "bye")
        save_files(folder, {"subf/file.txt": "HELLO!!",
                            "subf2/file2.txt": "BYE!!"})
        self.client.run('config install')
        content = load(os.path.join(self.client.cache_folder, "file.txt"))
        self.assertEqual(content, "HELLO!!")
        content = load(file2)
        self.assertEqual(content, "BYE!!")

    def test_dont_duplicate_configs(self):
        folder = temp_folder()
        save_files(folder, {"subf/file.txt": "hello"})
        self.client.run('config install "%s" -sf=subf' % folder)
        self.client.run('config install "%s" -sf=subf' % folder)
        content = load(self.client.cache.config_install_file)
        self.assertEqual(1, content.count("subf"))
        self.client.run('config install "%s" -sf=other' % folder)
        content = load(self.client.cache.config_install_file)
        self.assertEqual(1, content.count("subf"))
        self.assertEqual(1, content.count("other"))

    def test_install_registry_txt_error(self):
        folder = temp_folder()
        save_files(folder, {"registry.txt": "myrepo1 https://myrepourl.net False"})
        self.client.run('config install "%s"' % folder)
        self.assertIn("WARN: registry.txt has been deprecated. Migrating to remotes.json",
                      self.client.out)
        self.client.run("remote list")
        self.assertEqual("myrepo1: https://myrepourl.net [Verify SSL: False]\n", self.client.out)

    def test_install_registry_json_error(self):
        folder = temp_folder()
        registry_json = {"remotes": [{"url": "https://server.conan.io",
                                      "verify_ssl": True,
                                      "name": "conan.io"
                                      }]}
        save_files(folder, {"registry.json": json.dumps(registry_json)})
        self.client.run('config install "%s"' % folder)
        self.assertIn("WARN: registry.json has been deprecated. Migrating to remotes.json",
                      self.client.out)
        self.client.run("remote list")
        self.assertEqual("conan.io: https://server.conan.io [Verify SSL: True]\n", self.client.out)

    def test_install_remotes_json_error(self):
        folder = temp_folder()
        save_files(folder, {"remotes.json": ""})
        self.client.run('config install "%s"' % folder, assert_error=True)
        self.assertIn("ERROR: remotes.json install is not supported yet. Use 'remotes.txt'",
                      self.client.out)

    def test_without_profile_folder(self):
        shutil.rmtree(self.client.cache.profiles_path)
        zippath = self._create_zip()
        self.client.run('config install "%s"' % zippath)
        self.assertEqual(sorted(os.listdir(self.client.cache.profiles_path)),
                         sorted(["linux", "windows"]))
        self.assertEqual(load(os.path.join(self.client.cache.profiles_path, "linux")).splitlines(),
                         linux_profile.splitlines())

    def install_url_test(self):
        """ should install from a URL
        """

        def my_download(obj, url, filename, **kwargs):  # @UnusedVariable
            self._create_zip(filename)

        with patch.object(FileDownloader, 'download', new=my_download):
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check("url, http://myfakeurl.com/myconf.zip, True, None")

            # repeat the process to check
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check("url, http://myfakeurl.com/myconf.zip, True, None")

    def install_change_only_verify_ssl_test(self):
        def my_download(obj, url, filename, **kwargs):  # @UnusedVariable
            self._create_zip(filename)

        with patch.object(FileDownloader, 'download', new=my_download):
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check("url, http://myfakeurl.com/myconf.zip, True, None")

            # repeat the process to check
            self.client.run("config install http://myfakeurl.com/myconf.zip --verify-ssl=False")
            self._check("url, http://myfakeurl.com/myconf.zip, False, None")

    def failed_install_repo_test(self):
        """ should install from a git repo
        """
        self.client.run('config install notexistingrepo.git', assert_error=True)
        self.assertIn("ERROR: Can't clone repo", self.client.out)

    def failed_install_http_test(self):
        """ should install from a http zip
        """
        self.client.run("config set general.retry_wait=0")
        self.client.run('config install httpnonexisting', assert_error=True)
        self.assertIn("ERROR: Error while installing config from httpnonexisting", self.client.out)

    def install_repo_test(self):
        """ should install from a git repo
        """

        folder = self._create_profile_folder()
        with self.client.chdir(folder):
            self.client.run_command('git init .')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')

        self.client.run('config install "%s/.git"' % folder)
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, None" % check_path)

    def install_repo_relative_test(self):
        relative_folder = "./config"
        absolute_folder = os.path.join(self.client.current_folder, "config")
        mkdir(absolute_folder)
        folder = self._create_profile_folder(absolute_folder)
        with self.client.chdir(folder):
            self.client.run_command('git init .')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')

        self.client.run('config install "%s/.git"' % relative_folder)
        self._check("git, %s, True, None" % os.path.join("%s" % folder, ".git"))

    def install_custom_args_test(self):
        """ should install from a git repo
        """

        folder = self._create_profile_folder()
        with self.client.chdir(folder):
            self.client.run_command('git init .')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')

        self.client.run('config install "%s/.git" --args="-c init.templateDir=value"' % folder)
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, -c init.templateDir=value" % check_path)

    def force_git_type_test(self):
        client = TestClient()
        client.run('config install httpnonexisting --type=git', assert_error=True)
        self.assertIn("Can't clone repo", client.out)

    def reinstall_error_test(self):
        """ should use configured URL in conan.conf
        """
        self.client.run("config install", assert_error=True)
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

        with patch.object(FileDownloader, 'download', new=my_download):
            self.client.run("config install %s" % fake_url_with_credentials)

            # Check credentials are not displayed in output
            self.assertNotIn(fake_url_with_credentials, self.client.out)
            self.assertIn(fake_url_hidden_password, self.client.out)

            # Check credentials still stored in configuration
            self._check("url, %s, True, None" % fake_url_with_credentials)

    def ssl_verify_test(self):
        fake_url = "https://fakeurl.com/myconf.zip"

        def download_verify_false(obj, url, filename, **kwargs):  # @UnusedVariable
            self.assertFalse(obj.verify)
            self._create_zip(filename)

        def download_verify_true(obj, url, filename, **kwargs):  # @UnusedVariable
            self.assertTrue(obj.verify)
            self._create_zip(filename)

        with patch.object(FileDownloader, 'download', new=download_verify_false):
            self.client.run("config install %s --verify-ssl=False" % fake_url)

        with patch.object(FileDownloader, 'download', new=download_verify_true):
            self.client.run("config install %s --verify-ssl=True" % fake_url)

    def test_git_checkout_is_possible(self):
        folder = self._create_profile_folder()
        with self.client.chdir(folder):
            self.client.run_command('git init .')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')
            self.client.run_command('git checkout -b other_branch')
            save(os.path.join(folder, "hooks", "cust", "cust.py"), "")
            self.client.run_command('git add .')
            self.client.run_command('git commit -m "my file"')
            self.client.run_command('git tag 0.0.1')
            self.client.run_command('git checkout master')

        # Without checkout
        self.client.run('config install "%s/.git"' % folder)
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, None" % check_path)
        file_path = os.path.join(self.client.cache.hooks_path, "cust", "cust.py")
        self.assertFalse(os.path.exists(file_path))
        # With checkout tag and reuse url
        self.client.run('config install --args="-b 0.0.1"')
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, -b 0.0.1" % check_path)
        self.assertTrue(os.path.exists(file_path))
        # With checkout branch and reuse url
        self.client.run('config install --args="-b other_branch"')
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, -b other_branch" % check_path)
        self.assertTrue(os.path.exists(file_path))
        # Add changes to that branch and update
        with self.client.chdir(folder):
            self.client.run_command('git checkout other_branch')
            save(os.path.join(folder, "hooks", "other", "other.py"), "")
            self.client.run_command('git add .')
            self.client.run_command('git commit -m "my other file"')
            self.client.run_command('git checkout master')
        other_path = os.path.join(self.client.cache_folder, "hooks", "other", "other.py")
        self.assertFalse(os.path.exists(other_path))
        self.client.run('config install')
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, -b other_branch" % check_path)
        self.assertTrue(os.path.exists(other_path))

    def test_config_install_requester(self):
        # https://github.com/conan-io/conan/issues/4169
        http_server = StoppableThreadBottle()
        path = self._create_zip()

        from bottle import static_file

        @http_server.server.get("/myconfig.zip")
        def get_zip():
            return static_file(os.path.basename(path), os.path.dirname(path))

        http_server.run_server()
        self.client.run("config install http://localhost:%s/myconfig.zip" % http_server.port)
        self.assertIn("Unzipping", self.client.out)
        http_server.stop()
