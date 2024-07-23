import os
import shutil
import stat
import textwrap
import unittest

import pytest
from mock import patch

from conan.api.model import Remote
from conans.client.conf.config_installer import _hide_password
from conans.client.downloaders.file_downloader import FileDownloader
from conan.internal.paths import DEFAULT_CONAN_HOME
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import scan_folder, temp_folder, tgz_with_contents
from conan.test.utils.tools import TestClient, zipdir
from conans.util.files import load, mkdir, save, save_files


def make_file_read_only(file_path):
    mode = os.stat(file_path).st_mode
    os.chmod(file_path, mode & ~ stat.S_IWRITE)


win_profile = """[settings]
    os: Windows
"""

linux_profile = """[settings]
    os: Linux
"""

remotes = """{
 "remotes": [
  {
   "name": "myrepo1",
   "url": "https://myrepourl.net",
   "verify_ssl": false
  },
  {
   "name": "my-repo-2",
   "url": "https://myrepo2.com",
   "verify_ssl": true
  }
 ]
}
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
cpu_count = 1             # environment CONAN_CPU_COUNT

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


class ConfigInstallTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient()
        save(os.path.join(self.client.cache.profiles_path, "default"), "#default profile empty")
        save(os.path.join(self.client.cache.profiles_path, "linux"), "#empty linux profile")

    @staticmethod
    def _create_profile_folder(folder=None):
        folder = folder or temp_folder(path_with_spaces=False)
        save_files(folder, {"settings.yml": settings_yml,
                            "remotes.json": remotes,
                            "profiles/linux": linux_profile,
                            "profiles/windows": win_profile,
                            "hooks/dummy": "#hook dummy",
                            "hooks/foo.py": "#hook foo",
                            "hooks/custom/custom.py": "#hook custom",
                            ".git/hooks/foo": "foo",
                            "hooks/.git/hooks/before_push": "before_push",
                            "pylintrc": "#Custom pylint",
                            "python/myfuncs.py": myfuncpy,
                            "python/__init__.py": ""
                            })
        return folder

    def test_config_fails_no_storage(self):
        folder = temp_folder(path_with_spaces=False)
        save_files(folder, {"remotes.json": remotes})
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkg --version=1.0")
        client.run('config install "%s"' % folder)
        client.run("remote list")
        self.assertIn("myrepo1: https://myrepourl.net [Verify SSL: False, Enabled: True]",
                      client.out)
        self.assertIn("my-repo-2: https://myrepo2.com [Verify SSL: True, Enabled: True]", client.out)

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
        settings_path = self.client.cache.settings_path
        self.assertEqual(load(settings_path).splitlines(), settings_yml.splitlines())
        api = self.client.api
        cache_remotes = api.remotes.list()
        self.assertEqual(list(cache_remotes), [
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
        src_remote_file = os.path.join(profile_folder, "remotes.json")

        # Install profile_folder without settings.yml + remotes.json in order to install them manually
        tmp_dir = tempfile.mkdtemp()
        dest_setting_file = os.path.join(tmp_dir, "settings.yml")
        dest_remote_file = os.path.join(tmp_dir, "remotes.json")
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

        # remotes.txt is ignored
        save_files(folder, {"remotes.json": remotes_json,
                            "remotes.txt": remotes_txt})

        self.client.run(f'config install "{folder}"')
        assert "Defining remotes from remotes.json" in self.client.out

        self.client.run('remote list')

        assert "repojson1: https://repojson1.net [Verify SSL: False, Enabled: True]" in self.client.out
        assert "repojson2: https://repojson2.com [Verify SSL: True, Enabled: True]" in self.client.out

        # We only install remotes.json
        folder = temp_folder()
        save_files(folder, {"remotes.json": remotes_json})

        self.client.run(f'config install "{folder}"')
        assert "Defining remotes from remotes.json" in self.client.out

        self.client.run('remote list')

        assert "repojson1: https://repojson1.net [Verify SSL: False, Enabled: True]" in self.client.out
        assert "repojson2: https://repojson2.com [Verify SSL: True, Enabled: True]" in self.client.out

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
        self.client.run('config install httpnonexisting', assert_error=True)
        self.assertIn("ERROR: Failed conan config install: "
                      "Error while installing config from httpnonexisting", self.client.out)

    @pytest.mark.tool("git")
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

    @pytest.mark.tool("git")
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

    @pytest.mark.tool("git")
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
            assert kwargs["verify_ssl"] is False
            self._create_zip(file_path)

        def download_verify_true(obj, url, file_path, **kwargs):  # @UnusedVariable
            assert kwargs["verify_ssl"] is True
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=download_verify_false):
            self.client.run("config install %s --verify-ssl=False" % fake_url)

        with patch.object(FileDownloader, 'download', new=download_verify_true):
            self.client.run("config install %s --verify-ssl=True" % fake_url)

        with patch.object(FileDownloader, 'download', new=download_verify_true):
            self.client.run(f"config install {fake_url}")

        with patch.object(FileDownloader, 'download', new=download_verify_false):
            self.client.run(f"config install {fake_url} --insecure")

    @pytest.mark.tool("git")
    def test_git_checkout_is_possible(self):
        folder = self._create_profile_folder()
        with self.client.chdir(folder):
            self.client.run_command('git init .')
            self.client.run_command('git checkout -b master')
            self.client.run_command('git add .')
            self.client.run_command('git config user.name myname')
            self.client.run_command('git config user.email myname@mycompany.com')
            self.client.run_command('git commit -m "mymsg"')
            self.client.run_command('git checkout -b other_branch')
            save(os.path.join(folder, "extensions", "hooks", "cust", "cust.py"), "")
            self.client.run_command('git add .')
            self.client.run_command('git commit -m "my file"')

        self.client.run('config install "%s/.git" --args "-b other_branch"' % folder)
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, -b other_branch" % check_path)
        file_path = os.path.join(self.client.cache.hooks_path, "cust", "cust.py")
        assert load(file_path) == ""

        # Add changes to that branch and update
        with self.client.chdir(folder):
            save(os.path.join(folder, "extensions", "hooks", "cust", "cust.py"), "new content")
            self.client.run_command('git add .')
            self.client.run_command('git commit -m "my other file"')
            self.client.run_command('git checkout master')
        self.client.run('config install "%s/.git" --args "-b other_branch"' % folder)
        check_path = os.path.join(folder, ".git")
        self._check("git, %s, True, -b other_branch" % check_path)
        assert load(file_path) == "new content"

    def test_config_install_requester(self):
        # https://github.com/conan-io/conan/issues/4169
        path = self._create_zip()
        file_server = TestFileServer(os.path.dirname(path))
        self.client.servers["file_server"] = file_server

        self.client.run(f"config install {file_server.fake_url}/myconfig.zip")
        assert "Defining remotes from remotes.json" in self.client.out
        assert "Copying file myfuncs.py" in self.client.out


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
        make_file_read_only(os.path.join(source_folder, 'remotes.json'))

        self.client.run('config install "%s"' % source_folder)
        self.assertTrue(os.access(self.client.cache.settings_path, os.W_OK))


class ConfigInstallSchedTest(unittest.TestCase):

    def setUp(self):
        self.folder = temp_folder(path_with_spaces=False)
        # FIXME: This is broken, this config no longer exist, but it doesn't raise, fix it
        save_files(self.folder, {"global.conf": "core:config_install_interval=5m"})
        self.client = TestClient()
        self.client.save({"conanfile.txt": ""})

    def test_execute_more_than_once(self):
        """ Once executed by the scheduler, conan config install must executed again
            when invoked manually
        """
        self.client.run('config install "%s"' % self.folder)
        self.assertIn("Copying file global.conf", self.client.out)

        self.client.run('config install "%s"' % self.folder)
        self.assertIn("Copying file global.conf", self.client.out)

    @pytest.mark.tool("git")
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
        self.assertIn("Copying file global.conf", self.client.out)
        self.assertIn("Repo cloned!", self.client.out)  # git clone executed by scheduled task

    def test_config_fails_git_folder(self):
        # https://github.com/conan-io/conan/issues/8594
        folder = os.path.join(temp_folder(), ".gitlab-conan", DEFAULT_CONAN_HOME)
        client = TestClient(cache_folder=folder)
        with client.chdir(self.folder):
            client.run_command('git init .')
            client.run_command('git add .')
            client.run_command('git config user.name myname')
            client.run_command('git config user.email myname@mycompany.com')
            client.run_command('git commit -m "mymsg"')
        assert ".gitlab-conan" in client.cache_folder
        assert os.path.basename(client.cache_folder) == DEFAULT_CONAN_HOME
        client.run('config install "%s/.git" --type git' % self.folder)
        conf = load(client.cache.new_config_path)
        dirs = os.listdir(client.cache_folder)
        assert ".git" not in dirs


class TestConfigInstall:
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


class TestConfigInstallPkg:
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class Conf(ConanFile):
            name = "myconf"
            version = "0.1"
            package_type = "configuration"
            def package(self):
                copy(self, "*.conf", src=self.build_folder, dst=self.package_folder)
            """)

    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "global.conf": "user.myteam:myconf=myvalue"})
        c.run("export-pkg .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c

    def test_config_install_from_pkg(self, client):
        # Now install it
        c = client
        c.run("config install-pkg myconf/[*]")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: myvalue" in c.out

        # Just to make sure it doesn't crash in the update
        c.run("config install-pkg myconf/[*]")
        # Conan will not re-download fromthe server the same revision
        assert "myconf/0.1: Downloaded package revision" not in c.out
        # It doesn't re-install either
        assert "Copying file global.conf" not in c.out
        c.run("config show *")
        assert "user.myteam:myconf: myvalue" in c.out

        # We can force the re-installation
        c.run("config install-pkg myconf/[*] --force")
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: myvalue" in c.out

    def test_update_flow(self, client):
        # Now try the update flow
        c = client
        c2 = TestClient(servers=c.servers, inputs=["admin", "password"])
        c2.save({"conanfile.py": self.conanfile,
                 "global.conf": "user.myteam:myconf=othervalue"})
        c2.run("export-pkg .")
        c2.run("upload * -r=default -c")

        c.run("config install-pkg myconf/[*]")
        assert "myconf/0.1: Downloaded package revision" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: othervalue" in c.out

    def test_cant_use_as_dependency(self):
        c = TestClient()
        conanfile = GenConanfile("myconf", "0.1").with_package_type("configuration")
        c.save({"myconf/conanfile.py": conanfile,
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("myconf/0.1")})
        c.run("create myconf")
        c.run("install pkg", assert_error=True)
        assert "ERROR: Configuration package myconf/0.1 cannot be used as requirement, " \
               "but pkg/0.1 is requiring it" in c.out

    def test_cant_use_without_type(self):
        c = TestClient()
        conanfile = GenConanfile("myconf", "0.1")
        c.save({"myconf/conanfile.py": conanfile})
        c.run("create myconf")
        c.run("config install-pkg myconf/[*]", assert_error=True)
        assert 'ERROR: myconf/0.1 is not of package_type="configuration"' in c.out

    def test_lockfile(self, client):
        """ it should be able to install the config using a lockfile
        """
        c = client
        c.run("config install-pkg myconf/[*] --lockfile-out=config.lock")

        c2 = TestClient(servers=c.servers, inputs=["admin", "password"])
        # Make sure we bump the version, otherwise only a package revision will be created
        c2.save({"conanfile.py": self.conanfile.replace("0.1", "0.2"),
                 "global.conf": "user.myteam:myconf=othervalue"})
        c2.run("export-pkg .")
        c2.run("upload * -r=default -c")

        c.run("config install-pkg myconf/[*] --lockfile=config.lock")
        c.run("config show *")
        assert "user.myteam:myconf: myvalue" in c.out

    def test_create_also(self):
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import copy
           class Conf(ConanFile):
               name = "myconf"
               version = "0.1"
               package_type = "configuration"
               exports_sources = "*.conf"
               def package(self):
                   copy(self, "*.conf", src=self.build_folder, dst=self.package_folder)
               """)

        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": conanfile,
                "global.conf": "user.myteam:myconf=myvalue"})
        c.run("create .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")

        c.run("config install-pkg myconf/[*]")
        c.run("config show *")
        assert "user.myteam:myconf: myvalue" in c.out
