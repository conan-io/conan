import json
import os
import shutil
import tarfile
import textwrap
import time
import unittest

import pytest
import six
from mock import patch
from parameterized import parameterized

from conans.client.cache.remote_registry import Remote
from conans.client.conf import ConanClientConfigParser
from conans.client.conf.config_installer import _hide_password, _ConfigOrigin
from conans.client.downloaders.file_downloader import FileDownloader
from conans.errors import ConanException
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import scan_folder, temp_folder, tgz_with_contents
from conans.test.utils.tools import TestClient, StoppableThreadBottle, zipdir
from conans.util.files import load, mkdir, save, save_files, make_file_read_only

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

cache_conan_conf = """
[log]
run_to_output = False       # environment CONAN_LOG_RUN_TO_OUTPUT
level = 10                  # environment CONAN_LOGGING_LEVEL

[general]
compression_level = 6                 # environment CONAN_COMPRESSION_LEVEL
cpu_count = 1             # environment CONAN_CPU_COUNT
default_package_id_mode = full_package_mode # environment CONAN_DEFAULT_PACKAGE_ID_MODE

[proxies]
# Empty (or missing) section will try to use system proxies.
# As documented in https://requests.readthedocs.io/en/master/user/advanced/#proxies
http = http://user:pass@10.10.1.10:3128/
https = None
# http = http://10.10.1.10:3128
# https = http://10.10.1.10:1080
"""

myfuncpy = """def mycooladd(a, b):
    return a + b
"""

conanconf_interval = """
[general]
config_install_interval = 5m
"""


class ConfigInstallTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient()
        save(os.path.join(self.client.cache.profiles_path, "default"), "#default profile empty")
        save(os.path.join(self.client.cache.profiles_path, "linux"), "#empty linux profile")

    @staticmethod
    def _create_profile_folder(folder=None):
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
                            "config/conan.conf": cache_conan_conf,
                            "pylintrc": "#Custom pylint",
                            "python/myfuncs.py": myfuncpy,
                            "python/__init__.py": ""
                            })
        return folder

    def test_config_hooks(self):
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

    def test_config_fails_no_storage(self):
        folder = temp_folder(path_with_spaces=False)
        save_files(folder, {"remotes.txt": remotes})
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@")
        conf = load(client.cache.conan_conf_path)
        conf = conf.replace("path = ./data", "")
        save(client.cache.conan_conf_path, conf)
        client.run('config install "%s"' % folder)
        client.run("remote list")
        self.assertIn("myrepo1: https://myrepourl.net [Verify SSL: False]", client.out)
        self.assertIn("my-repo-2: https://myrepo2.com [Verify SSL: True]", client.out)

    def _create_zip(self, zippath=None):
        folder = self._create_profile_folder()
        zippath = zippath or os.path.join(folder, "myconfig.zip")
        zipdir(folder, zippath)
        return zippath

    @staticmethod
    def _get_files(folder):
        relpaths = scan_folder(folder)
        files = {}
        for path in relpaths:
            with open(os.path.join(folder, path), "r") as file_handle:
                files[path] = file_handle.read()
        return files

    def _create_tgz(self, tgz_path=None):
        folder = self._create_profile_folder()
        tgz_path = tgz_path or os.path.join(folder, "myconfig.tar.gz")
        files = self._get_files(folder)
        return tgz_with_contents(files, tgz_path)

    def _check(self, params):
        typ, uri, verify, args = [p.strip() for p in params.split(",")]
        configs = json.loads(load(self.client.cache.config_install_file))
        config = _ConfigOrigin(configs[-1])  # Check the last one
        self.assertEqual(config.type, typ)
        self.assertEqual(config.uri, uri)
        self.assertEqual(str(config.verify_ssl), verify)
        self.assertEqual(str(config.args), args)
        settings_path = self.client.cache.settings_path
        self.assertEqual(load(settings_path).splitlines(), settings_yml.splitlines())
        cache_remotes = self.client.cache.registry.load_remotes()
        self.assertEqual(list(cache_remotes.values()), [
            Remote("myrepo1", "https://myrepourl.net", False, False),
            Remote("my-repo-2", "https://myrepo2.com", True, False),
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

    def test_reuse_python(self):
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

    def test_install_file(self):
        """ should install from a file in current dir
        """
        zippath = self._create_zip()
        for filetype in ["", "--type=file"]:
            self.client.run('config install "%s" %s' % (zippath, filetype))
            self._check("file, %s, True, None" % zippath)
            self.assertTrue(os.path.exists(zippath))

    def test_install_config_file(self):
        """ should install from a settings and remotes file in configuration directory
        """
        import tempfile
        profile_folder = self._create_profile_folder()
        self.assertTrue(os.path.isdir(profile_folder))
        src_setting_file = os.path.join(profile_folder, "settings.yml")
        src_remote_file = os.path.join(profile_folder, "remotes.txt")

        # Install profile_folder without settings.yml + remotes.txt in order to install them manually
        tmp_dir = tempfile.mkdtemp()
        dest_setting_file = os.path.join(tmp_dir, "settings.yml")
        dest_remote_file = os.path.join(tmp_dir, "remotes.txt")
        shutil.move(src_setting_file, dest_setting_file)
        shutil.move(src_remote_file, dest_remote_file)
        self.client.run('config install "%s"' % profile_folder)
        shutil.move(dest_setting_file, src_setting_file)
        shutil.move(dest_remote_file, src_remote_file)
        shutil.rmtree(tmp_dir)

        for cmd_option in ["", "--type=file"]:
            self.client.run('config install "%s" %s' % (src_setting_file, cmd_option))
            self.client.run('config install "%s" %s' % (src_remote_file, cmd_option))
            self._check("file, %s, True, None" % src_remote_file)

    def test_install_dir(self):
        """ should install from a dir in current dir
        """
        folder = self._create_profile_folder()
        self.assertTrue(os.path.isdir(folder))
        for dirtype in ["", "--type=dir"]:
            self.client.run('config install "%s" %s' % (folder, dirtype))
            self._check("dir, %s, True, None" % folder)

    def test_install_source_target_folders(self):
        folder = temp_folder()
        save_files(folder, {"subf/file.txt": "hello",
                            "subf/subf/file2.txt": "bye"})
        self.client.run('config install "%s" -sf=subf -tf=newsubf' % folder)
        content = load(os.path.join(self.client.cache_folder, "newsubf/file.txt"))
        self.assertEqual(content, "hello")
        content = load(os.path.join(self.client.cache_folder, "newsubf/subf/file2.txt"))
        self.assertEqual(content, "bye")

    def test_install_multiple_configs(self):
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

    def test_install_remotes_json(self):
        folder = temp_folder()

        remotes_json = textwrap.dedent("""
            {
                "remotes": [
                    { "name": "repojson1", "url": "https://repojson1.net", "verify_ssl": false },
                    { "name": "repojson2", "url": "https://repojson2.com", "verify_ssl": true }
                ]
            }
        """)

        remotes_txt = textwrap.dedent("""\
            repotxt1 https://repotxt1.net False
            repotxt2 https://repotxt2.com True
        """)

        # remotes.txt and json try to define both the remotes,
        # could lead to unpredictable results
        save_files(folder, {"remotes.json": remotes_json,
                            "remotes.txt": remotes_txt})

        self.client.run(f'config install "{folder}"')
        assert "Defining remotes from remotes.json" in self.client.out
        assert "Defining remotes from remotes.txt" in self.client.out

        # If there's only a remotes.txt it's the one installed
        folder = temp_folder()
        save_files(folder, {"remotes.txt": remotes_txt})

        self.client.run(f'config install "{folder}"')

        assert "Defining remotes from remotes.txt" in self.client.out

        self.client.run('remote list')

        assert "repotxt1: https://repotxt1.net [Verify SSL: False]" in self.client.out
        assert "repotxt2: https://repotxt2.com [Verify SSL: True]" in self.client.out

        # If there's only a remotes.json it's the one installed
        folder = temp_folder()
        save_files(folder, {"remotes.json": remotes_json})

        self.client.run(f'config install "{folder}"')
        assert "Defining remotes from remotes.json" in self.client.out

        self.client.run('remote list')

        assert "repojson1: https://repojson1.net [Verify SSL: False]" in self.client.out
        assert "repojson2: https://repojson2.com [Verify SSL: True]" in self.client.out

    def test_without_profile_folder(self):
        shutil.rmtree(self.client.cache.profiles_path)
        zippath = self._create_zip()
        self.client.run('config install "%s"' % zippath)
        self.assertEqual(sorted(os.listdir(self.client.cache.profiles_path)),
                         sorted(["linux", "windows"]))
        self.assertEqual(load(os.path.join(self.client.cache.profiles_path, "linux")).splitlines(),
                         linux_profile.splitlines())

    def test_install_url(self):
        """ should install from a URL
        """

        for origin in ["", "--type=url"]:
            def my_download(obj, url, file_path, **kwargs):  # @UnusedVariable
                self._create_zip(file_path)

            with patch.object(FileDownloader, 'download', new=my_download):
                self.client.run("config install http://myfakeurl.com/myconf.zip %s" % origin)
                self._check("url, http://myfakeurl.com/myconf.zip, True, None")

                # repeat the process to check
                self.client.run("config install http://myfakeurl.com/myconf.zip %s" % origin)
                self._check("url, http://myfakeurl.com/myconf.zip, True, None")

    def test_install_url_query(self):
        """ should install from a URL
        """

        def my_download(obj, url, file_path, **kwargs):  # @UnusedVariable
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=my_download):
            # repeat the process to check it works with ?args
            self.client.run("config install http://myfakeurl.com/myconf.zip?sha=1")
            self._check("url, http://myfakeurl.com/myconf.zip?sha=1, True, None")

    def test_install_change_only_verify_ssl(self):
        def my_download(obj, url, file_path, **kwargs):  # @UnusedVariable
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=my_download):
            self.client.run("config install http://myfakeurl.com/myconf.zip")
            self._check("url, http://myfakeurl.com/myconf.zip, True, None")

            # repeat the process to check
            self.client.run("config install http://myfakeurl.com/myconf.zip --verify-ssl=False")
            self._check("url, http://myfakeurl.com/myconf.zip, False, None")

    def test_install_url_tgz(self):
        """ should install from a URL to tar.gz
        """

        def my_download(obj, url, file_path, **kwargs):  # @UnusedVariable
            self._create_tgz(file_path)

        with patch.object(FileDownloader, 'download', new=my_download):
            self.client.run("config install http://myfakeurl.com/myconf.tar.gz")
            self._check("url, http://myfakeurl.com/myconf.tar.gz, True, None")

    def test_failed_install_repo(self):
        """ should install from a git repo
        """
        self.client.run('config install notexistingrepo.git', assert_error=True)
        self.assertIn("ERROR: Failed conan config install: Can't clone repo", self.client.out)

    def test_failed_install_http(self):
        """ should install from a http zip
        """
        self.client.run("config set general.retry_wait=0")
        self.client.run('config install httpnonexisting', assert_error=True)
        self.assertIn("ERROR: Failed conan config install: "
                      "Error while installing config from httpnonexisting", self.client.out)

    @pytest.mark.tool_git
    def test_install_repo(self):
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

    @pytest.mark.tool_git
    def test_install_repo_relative(self):
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

    @pytest.mark.tool_git
    def test_install_custom_args(self):
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

    def test_force_git_type(self):
        client = TestClient()
        client.run('config install httpnonexisting --type=git', assert_error=True)
        self.assertIn("Can't clone repo", client.out)

    def test_force_dir_type(self):
        client = TestClient()
        client.run('config install httpnonexisting --type=dir', assert_error=True)
        self.assertIn("ERROR: Failed conan config install: No such directory: 'httpnonexisting'",
                      client.out)

    def test_force_file_type(self):
        client = TestClient()
        client.run('config install httpnonexisting --type=file', assert_error=True)
        self.assertIn("No such file or directory: 'httpnonexisting'", client.out)

    def test_force_url_type(self):
        client = TestClient()
        client.run('config install httpnonexisting --type=url', assert_error=True)
        self.assertIn("Error downloading file httpnonexisting: 'Invalid URL 'httpnonexisting'",
                      client.out)

    def test_reinstall_error(self):
        """ should use configured URL in conan.conf
        """
        self.client.run("config install", assert_error=True)
        self.assertIn("Called config install without arguments", self.client.out)

    def test_removed_credentials_from_url_unit(self):
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

    def test_remove_credentials_config_installer(self):
        """ Functional test to check credentials are not displayed in output but are still present
        in conan configuration
        # https://github.com/conan-io/conan/issues/2324
        """
        fake_url_with_credentials = "http://test_user:test_password@myfakeurl.com/myconf.zip"
        fake_url_hidden_password = "http://test_user:<hidden>@myfakeurl.com/myconf.zip"

        def my_download(obj, url, file_path, **kwargs):  # @UnusedVariable
            self.assertEqual(url, fake_url_with_credentials)
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=my_download):
            self.client.run("config install %s" % fake_url_with_credentials)

            # Check credentials are not displayed in output
            self.assertNotIn(fake_url_with_credentials, self.client.out)
            self.assertIn(fake_url_hidden_password, self.client.out)

            # Check credentials still stored in configuration
            self._check("url, %s, True, None" % fake_url_with_credentials)

    def test_ssl_verify(self):
        fake_url = "https://fakeurl.com/myconf.zip"

        def download_verify_false(obj, url, file_path, **kwargs):  # @UnusedVariable
            self.assertFalse(obj._verify_ssl)
            self._create_zip(file_path)

        def download_verify_true(obj, url, file_path, **kwargs):  # @UnusedVariable
            self.assertTrue(obj._verify_ssl)
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=download_verify_false):
            self.client.run("config install %s --verify-ssl=False" % fake_url)

        with patch.object(FileDownloader, 'download', new=download_verify_true):
            self.client.run("config install %s --verify-ssl=True" % fake_url)

    @pytest.mark.tool_git
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

    def test_error_missing_origin(self):
        path = self._create_zip()
        self.client.run('config install "%s"' % path)
        os.remove(path)
        self.client.run('config install', assert_error=True)
        self.assertIn("ERROR: Failed conan config install", self.client.out)

    def test_list_remove(self):
        path = self._create_zip()
        self.client.run('config install "%s"' % path)
        configs = json.loads(load(os.path.join(self.client.cache_folder, "config_install.json")))
        self.assertIn("myconfig.zip", configs[0]["uri"])
        self.client.run("config install --list")
        self.assertIn("myconfig.zip", self.client.out)
        self.client.run("config install --remove=0")
        configs = json.loads(load(os.path.join(self.client.cache_folder, "config_install.json")))
        self.assertEqual(0, len(configs))
        self.client.run("config install --list")
        self.assertNotIn("myconfig.zip", self.client.out)

    def test_list_empty_config(self):
        self.client.run("config install --list")
        self.assertEqual("", self.client.out)

    def test_remove_empty_config(self):
        self.client.run("config install --remove=0", assert_error=True)
        self.assertIn("There is no config data. Need to install config first.", self.client.out)

    def test_overwrite_read_only_file(self):
        source_folder = self._create_profile_folder()
        self.client.run('config install "%s"' % source_folder)
        # make existing settings.yml read-only
        make_file_read_only(self.client.cache.settings_path)
        self.assertFalse(os.access(self.client.cache.settings_path, os.W_OK))

        # config install should overwrite the existing read-only file
        self.client.run('config install "%s"' % source_folder)
        self.assertTrue(os.access(self.client.cache.settings_path, os.W_OK))

    def test_dont_copy_file_permissions(self):
        source_folder = self._create_profile_folder()
        # make source settings.yml read-only
        make_file_read_only(os.path.join(source_folder, 'remotes.txt'))

        self.client.run('config install "%s"' % source_folder)
        self.assertTrue(os.access(self.client.cache.settings_path, os.W_OK))


class ConfigInstallSchedTest(unittest.TestCase):

    def setUp(self):
        self.folder = temp_folder(path_with_spaces=False)
        save_files(self.folder, {"conan.conf": conanconf_interval})
        self.client = TestClient()
        self.client.save({"conanfile.txt": ""})

    def test_config_install_sched_file(self):
        """ Config install can be executed without restriction
        """
        self.client.run('config install "%s"' % self.folder)
        self.assertIn("Processing conan.conf", self.client.out)
        content = load(self.client.cache.conan_conf_path)
        self.assertEqual(1, content.count("config_install_interval"))
        self.assertIn("config_install_interval = 5m", content.splitlines())
        self.assertTrue(os.path.exists(self.client.cache.config_install_file))
        self.assertLess(os.path.getmtime(self.client.cache.config_install_file), time.time() + 1)

    def test_execute_more_than_once(self):
        """ Once executed by the scheduler, conan config install must executed again
            when invoked manually
        """
        self.client.run('config install "%s"' % self.folder)
        self.assertIn("Processing conan.conf", self.client.out)

        self.client.run('config install "%s"' % self.folder)
        self.assertIn("Processing conan.conf", self.client.out)
        self.assertLess(os.path.getmtime(self.client.cache.config_install_file), time.time() + 1)

    def test_sched_timeout(self):
        """ Conan config install must be executed when the scheduled time reaches
        """
        self.client.run('config install "%s"' % self.folder)
        self.client.run('config set general.config_install_interval=1m')
        self.assertNotIn("Processing conan.conf", self.client.out)
        past_time = int(time.time() - 120)  # 120 seconds in the past
        os.utime(self.client.cache.config_install_file, (past_time, past_time))

        self.client.run('search')  # any command will fire it
        self.assertIn("Processing conan.conf", self.client.out)
        self.client.run('search')  # not again, it was fired already
        self.assertNotIn("Processing conan.conf", self.client.out)
        self.client.run('config get general.config_install_interval')
        self.assertNotIn("Processing conan.conf", self.client.out)
        self.assertIn("5m", self.client.out)  # The previous 5 mins has been restored!

    def test_invalid_scheduler(self):
        """ An exception must be raised when conan_config.json is not listed
        """
        self.client.run('config install "%s"' % self.folder)
        os.remove(self.client.cache.config_install_file)
        self.client.run('config get general.config_install_interval', assert_error=True)
        self.assertIn("config_install_interval defined, but no config_install file", self.client.out)

    @parameterized.expand([("1y",), ("2015t",), ("42",)])
    def test_invalid_time_interval(self, internal):
        """ config_install_interval only accepts seconds, minutes, hours, days and weeks.
        """
        self.client.run('config set general.config_install_interval={}'.format(internal))
        # Any conan invocation will fire the configuration error
        self.client.run('install .', assert_error=True)
        self.assertIn("ERROR: Incorrect definition of general.config_install_interval: {}. "
                      "Removing it from conan.conf to avoid possible loop error.".format(internal),
                      self.client.out)
        self.client.run('install .')

    @pytest.mark.tool_git
    def test_config_install_remove_git_repo(self):
        """ config_install_interval must break when remote git has been removed
        """
        with self.client.chdir(self.folder):
            self.client.run_command('git init .')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')
        self.client.run('config install "%s/.git" --type git' % self.folder)
        self.assertIn("Processing conan.conf", self.client.out)
        self.assertIn("Repo cloned!", self.client.out)  # git clone executed by scheduled task
        folder_name = self.folder
        new_name = self.folder + "_test"
        os.rename(self.folder, new_name)
        with patch("conans.client.command.is_config_install_scheduled", return_value=True):
            self.client.run("config --help", assert_error=True)
            # scheduled task has been executed. Without a remote, the user should fix the config
            self.assertIn("ERROR: Failed conan config install: Can't clone repo", self.client.out)

            # restore the remote
            os.rename(new_name, folder_name)
            self.client.run("config --help")
            self.assertIn("Repo cloned!", self.client.out)

    @pytest.mark.tool_git
    def test_config_install_remove_config_repo(self):
        """ config_install_interval should not run when config list is empty
        """
        with self.client.chdir(self.folder):
            self.client.run_command('git init .')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')
        self.client.run('config install "%s/.git" --type git' % self.folder)
        self.assertIn("Processing conan.conf", self.client.out)
        self.assertIn("Repo cloned!", self.client.out)
        # force scheduled time for all commands
        with patch("conans.client.conf.config_installer._is_scheduled_intervals", return_value=True):
            self.client.run("config --help")
            self.assertIn("Repo cloned!", self.client.out)  # git clone executed by scheduled task

            # config install must not run scheduled config
            self.client.run("config install --remove 0")
            self.assertEqual("", self.client.out)
            self.client.run("config install --list")
            self.assertEqual("", self.client.out)

            last_change = os.path.getmtime(self.client.cache.config_install_file)
            # without a config in configs file, scheduler only emits a warning
            self.client.run("help")
            self.assertIn("WARN: Skipping scheduled config install, "
                          "no config listed in config_install file", self.client.out)
            self.assertNotIn("Repo cloned!", self.client.out)
            # ... and updates the next schedule
            self.assertGreater(os.path.getmtime(self.client.cache.config_install_file), last_change)

    def test_config_fails_git_folder(self):
        # https://github.com/conan-io/conan/issues/8594
        folder = os.path.join(temp_folder(), ".gitlab-conan", ".conan")
        client = TestClient(cache_folder=folder)
        with client.chdir(self.folder):
            client.run_command('git init .')
            client.run_command('git add .')
            client.run_command('git config user.name myname')
            client.run_command('git config user.email myname@mycompany.com')
            client.run_command('git commit -m "mymsg"')
        assert ".gitlab-conan" in client.cache_folder
        assert os.path.basename(client.cache_folder) == ".conan"
        conf = load(client.cache.conan_conf_path)
        assert "config_install_interval = 5m" not in conf
        client.run('config install "%s/.git" --type git' % self.folder)
        conf = load(client.cache.conan_conf_path)
        assert "config_install_interval = 5m" in conf
        dirs = os.listdir(client.cache.cache_folder)
        assert ".git" not in dirs

    def test_config_install_reestructuring_source(self):
        """  https://github.com/conan-io/conan/issues/9885 """

        folder = temp_folder()
        client = TestClient()
        with client.chdir(folder):
            client.save({"profiles/debug/address-sanitizer": ""})
            client.run("config install .")

        debug_cache_folder = os.path.join(client.cache_folder, "profiles", "debug")
        assert os.path.isdir(debug_cache_folder)

        # Now reestructure the files, what it was already a directory in the cache now we want
        # it to be a file
        folder = temp_folder()
        with client.chdir(folder):
            client.save({"profiles/debug": ""})
            client.run("config install .")
        assert os.path.isfile(debug_cache_folder)

        # And now is a directory again
        folder = temp_folder()
        with client.chdir(folder):
            client.save({"profiles/debug/address-sanitizer": ""})
            client.run("config install .")
        assert os.path.isdir(debug_cache_folder)
