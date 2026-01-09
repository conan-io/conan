import json
import os
import shutil
import stat
import textwrap

import pytest
from unittest.mock import patch

import yaml

from conan.api.model import Remote, RecipeReference
from conan.internal.api.config.config_installer import _hide_password

from conan.internal.cache.home_paths import HomePaths
from conan.internal.rest.file_downloader import FileDownloader
from conan.internal.paths import DEFAULT_CONAN_HOME
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import scan_folder, temp_folder, tgz_with_contents
from conan.test.utils.tools import TestClient, zipdir
from conan.internal.util.files import load, mkdir, save, save_files


def make_file_read_only(file_path):
    mode = os.stat(file_path).st_mode
    os.chmod(file_path, mode & ~ stat.S_IWRITE)


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


class TestConfigInstall:

    @staticmethod
    def _create_profile_folder(folder=None):
        folder = folder or temp_folder(path_with_spaces=False)
        save_files(folder, {"settings.yml": settings_yml,
                            "remotes.json": remotes,
                            "profiles/linux": "#linuxprofile",
                            "profiles/windows": "#winprofile",
                            "hooks/dummy": "#hook dummy",
                            "hooks/foo.py": "#hook foo",
                            "hooks/custom/custom.py": "#hook custom",
                            ".git/hooks/foo": "foo",
                            "hooks/.git/hooks/before_push": "before_push",
                            "pylintrc": "#Custom pylint",
                            "python/myfuncs.py": "does not matter",
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
        assert "myrepo1: https://myrepourl.net [Verify SSL: False, Enabled: True]" in client.out
        assert "my-repo-2: https://myrepo2.com [Verify SSL: True, Enabled: True]" in client.out

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

    @staticmethod
    def _check(c):
        settings_path = c.paths.settings_path
        assert load(settings_path).splitlines() == settings_yml.splitlines()
        api = c.api
        cache_remotes = api.remotes.list()
        assert list(cache_remotes) == [
            Remote("myrepo1", "https://myrepourl.net", False, False),
            Remote("my-repo-2", "https://myrepo2.com", True, False),
        ]
        assert sorted(os.listdir(c.paths.profiles_path)) == sorted(["default", "linux", "windows"])
        assert c.load_home("profiles/linux") == "#linuxprofile"
        assert c.load_home("profiles/windows") == "#winprofile"
        assert "#Custom pylint" == c.load_home("pylintrc")
        assert "" == c.load_home("python/__init__.py")
        assert "#hook dummy" == c.load_home("hooks/dummy")
        assert "#hook foo" == c.load_home("hooks/foo.py")
        assert "#hook custom" == c.load_home("hooks/custom/custom.py")
        assert not os.path.exists(os.path.join(c.cache_folder, "hooks", ".git"))
        assert not os.path.exists(os.path.join(c.cache_folder, ".git"))

    def test_install_file(self):
        """ should install from a file in current dir
        """
        zippath = self._create_zip()
        c = TestClient(light=True)
        for filetype in ["", "--type=file"]:
            c.run('config install "%s" %s' % (zippath, filetype))
            self._check(c)
            assert os.path.exists(zippath)

    def test_install_config_file(self):
        """ should install from a settings and remotes file in configuration directory
        """
        import tempfile
        profile_folder = self._create_profile_folder()
        assert os.path.isdir(profile_folder)
        src_setting_file = os.path.join(profile_folder, "settings.yml")
        src_remote_file = os.path.join(profile_folder, "remotes.json")

        # Install profile_folder without settings.yml remotes.json in order to install them manually
        tmp_dir = tempfile.mkdtemp()
        dest_setting_file = os.path.join(tmp_dir, "settings.yml")
        dest_remote_file = os.path.join(tmp_dir, "remotes.json")
        shutil.move(src_setting_file, dest_setting_file)
        shutil.move(src_remote_file, dest_remote_file)

        c = TestClient(light=True)
        c.run('config install "%s"' % profile_folder)
        shutil.move(dest_setting_file, src_setting_file)
        shutil.move(dest_remote_file, src_remote_file)
        shutil.rmtree(tmp_dir)

        for cmd_option in ["", "--type=file"]:
            c.run('config install "%s" %s' % (src_setting_file, cmd_option))
            c.run('config install "%s" %s' % (src_remote_file, cmd_option))
            self._check(c)

    def test_install_dir(self):
        """ should install from a dir in current dir
        """
        folder = self._create_profile_folder()
        assert os.path.isdir(folder)
        c = TestClient(light=True)
        for dirtype in ["", "--type=dir"]:
            c.run('config install "%s" %s' % (folder, dirtype))
            self._check(c)

    def test_install_source_target_folders(self):
        folder = temp_folder()
        save_files(folder, {"subf/file.txt": "hello",
                            "subf/subf/file2.txt": "bye"})
        c = TestClient(light=True)
        c.run('config install "%s" -sf=subf -tf=newsubf' % folder)
        content = c.load_home("newsubf/file.txt")
        assert content == "hello"
        content = c.load_home("newsubf/subf/file2.txt")
        assert content == "bye"

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

        c = TestClient(light=True)
        c.run(f'config install "{folder}"')
        assert "Defining remotes from remotes.json" in c.out

        c.run('remote list')

        assert "repojson1: https://repojson1.net [Verify SSL: False, Enabled: True]" in c.out
        assert "repojson2: https://repojson2.com [Verify SSL: True, Enabled: True]" in c.out

        # We only install remotes.json
        folder = temp_folder()
        save_files(folder, {"remotes.json": remotes_json})

        c.run(f'config install "{folder}"')
        assert "Defining remotes from remotes.json" in c.out

        c.run('remote list')

        assert "repojson1: https://repojson1.net [Verify SSL: False, Enabled: True]" in c.out
        assert "repojson2: https://repojson2.com [Verify SSL: True, Enabled: True]" in c.out

    def test_without_profile_folder(self):
        c = TestClient(light=True)
        shutil.rmtree(c.paths.profiles_path)
        zippath = self._create_zip()

        c.run('config install "%s"' % zippath)
        assert sorted(os.listdir(c.paths.profiles_path)) == sorted(["linux", "windows"])
        assert c.load_home("profiles/linux") == "#linuxprofile"

    def test_install_url(self):
        """ should install from a URL
        """
        c = TestClient(light=True)
        for origin in ["", "--type=url"]:
            def my_download(obj, url, file_path, **kwargs):  # noqa
                self._create_zip(file_path)

            with patch.object(FileDownloader, 'download', new=my_download):
                c.run("config install http://myfakeurl.com/myconf.zip %s" % origin)
                self._check(c)

                # repeat the process to check
                c.run("config install http://myfakeurl.com/myconf.zip %s" % origin)
                self._check(c)

    def test_install_url_query(self):
        """ should install from a URL
        """
        c = TestClient(light=True)

        def my_download(obj, url, file_path, **kwargs):  # noqa
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=my_download):
            # repeat the process to check it works with ?args
            c.run("config install http://myfakeurl.com/myconf.zip?sha=1")
            self._check(c)

    def test_install_change_only_verify_ssl(self):
        def my_download(obj, url, file_path, **kwargs):  # noqa
            self._create_zip(file_path)

        c = TestClient(light=True)
        with patch.object(FileDownloader, 'download', new=my_download):
            c.run("config install http://myfakeurl.com/myconf.zip")
            self._check(c)

            # repeat the process to check
            c.run("config install http://myfakeurl.com/myconf.zip --verify-ssl=False")
            self._check(c)

    def test_install_url_tgz(self):
        """ should install from a URL to tar.gz
        """
        c = TestClient(light=True)

        def my_download(obj, url, file_path, **kwargs):  # noqa
            self._create_tgz(file_path)

        with patch.object(FileDownloader, 'download', new=my_download):
            c.run("config install http://myfakeurl.com/myconf.tar.gz")
            self._check(c)

    def test_failed_install_repo(self):
        """ should install from a git repo
        """
        c = TestClient(light=True)
        c.run('config install notexistingrepo.git', assert_error=True)
        assert "ERROR: Failed conan config install: Can't clone repo" in c.out

    def test_failed_install_http(self):
        """ should install from a http zip
        """
        c = TestClient(light=True)
        c.run('config install httpnonexisting', assert_error=True)
        assert ("ERROR: Failed conan config install: "
                "Error while installing config from httpnonexisting") in c.out

    @pytest.mark.tool("git")
    def test_install_repo(self):
        """ should install from a git repo
        """
        c = TestClient(light=True)
        folder = self._create_profile_folder()
        with c.chdir(folder):
            c.run_command('git init .')
            c.run_command('git add .')
            c.run_command('git config user.name myname')
            c.run_command('git config user.email myname@mycompany.com')
            c.run_command('git commit -m "mymsg"')

        c.run('config install "%s/.git"' % folder)
        self._check(c)

    @pytest.mark.tool("git")
    def test_install_repo_relative(self):
        c = TestClient(light=True)
        relative_folder = "./config"
        absolute_folder = os.path.join(c.current_folder, "config")
        mkdir(absolute_folder)
        folder = self._create_profile_folder(absolute_folder)
        with c.chdir(folder):
            c.run_command('git init .')
            c.run_command('git add .')
            c.run_command('git config user.name myname')
            c.run_command('git config user.email myname@mycompany.com')
            c.run_command('git commit -m "mymsg"')

        c.run('config install "%s/.git"' % relative_folder)
        self._check(c)

    @pytest.mark.tool("git")
    def test_install_custom_args(self):
        """ should install from a git repo
        """
        c = TestClient(light=True)
        folder = self._create_profile_folder()
        with c.chdir(folder):
            c.run_command('git init .')
            c.run_command('git add .')
            c.run_command('git config user.name myname')
            c.run_command('git config user.email myname@mycompany.com')
            c.run_command('git commit -m "mymsg"')

        c.run('config install "%s/.git" --args="-c init.templateDir=value"' % folder)
        self._check(c)

    def test_force_git_type(self):
        client = TestClient(light=True)
        client.run('config install httpnonexisting --type=git', assert_error=True)
        assert "Can't clone repo" in client.out

    def test_force_dir_type(self):
        c = TestClient(light=True)
        c.run('config install httpnonexisting --type=dir', assert_error=True)
        assert "ERROR: Failed conan config install: No such directory: 'httpnonexisting'" in c.out

    def test_force_file_type(self):
        client = TestClient(light=True)
        client.run('config install httpnonexisting --type=file', assert_error=True)
        assert "No such file or directory: 'httpnonexisting'" in client.out

    def test_force_url_type(self):
        client = TestClient(light=True)
        client.run('config install httpnonexisting --type=url', assert_error=True)
        assert "Error downloading file httpnonexisting: 'Invalid URL 'httpnonexisting'" in client.out

    def test_removed_credentials_from_url_unit(self):
        """
        Unit tests to remove credentials in netloc from url when using basic auth
        # https://github.com/conan-io/conan/issues/2324
        """
        url_without_credentials = r"https://server.com/resource.zip"
        url_with_credentials = r"https://test_username:test_password_123@server.com/resource.zip"
        url_hidden_password = r"https://test_username:<hidden>@server.com/resource.zip"

        # Check url is the same when not using credentials
        assert _hide_password(url_without_credentials) == url_without_credentials

        # Check password is hidden using url with credentials
        assert _hide_password(url_with_credentials) == url_hidden_password

        # Check that it works with other protocols ftp
        ftp_with_credentials = r"ftp://test_username_ftp:test_password_321@server.com/resurce.zip"
        ftp_hidden_password = r"ftp://test_username_ftp:<hidden>@server.com/resurce.zip"
        assert _hide_password(ftp_with_credentials) == ftp_hidden_password

        # Check function also works for file paths *unix/windows
        unix_file_path = r"/tmp/test"
        assert _hide_password(unix_file_path) == unix_file_path
        windows_file_path = r"c:\windows\test"
        assert _hide_password(windows_file_path) == windows_file_path

        # Check works with empty string
        assert _hide_password('') == ''

    def test_remove_credentials_config_installer(self):
        """ Functional test to check credentials are not displayed in output but are still present
        in conan configuration
        # https://github.com/conan-io/conan/issues/2324
        """
        fake_url_with_credentials = "http://test_user:test_password@myfakeurl.com/myconf.zip"
        fake_url_hidden_password = "http://test_user:<hidden>@myfakeurl.com/myconf.zip"

        def my_download(obj, url, file_path, **kwargs):  # noqa
            assert url == fake_url_with_credentials
            self._create_zip(file_path)

        c = TestClient(light=True)
        with patch.object(FileDownloader, 'download', new=my_download):
            c.run("config install %s" % fake_url_with_credentials)

            # Check credentials are not displayed in output
            assert fake_url_with_credentials not in c.out
            assert fake_url_hidden_password in c.out

            # Check credentials still stored in configuration
            self._check(c)

    def test_ssl_verify(self):
        c = TestClient(light=True)

        fake_url = "https://fakeurl.com/myconf.zip"

        def download_verify_false(obj, url, file_path, **kwargs):  # noqa
            assert kwargs["verify_ssl"] is False
            self._create_zip(file_path)

        def download_verify_true(obj, url, file_path, **kwargs):  # noqa
            assert kwargs["verify_ssl"] is True
            self._create_zip(file_path)

        with patch.object(FileDownloader, 'download', new=download_verify_false):
            c.run("config install %s --verify-ssl=False" % fake_url)

        with patch.object(FileDownloader, 'download', new=download_verify_true):
            c.run("config install %s --verify-ssl=True" % fake_url)

        with patch.object(FileDownloader, 'download', new=download_verify_true):
            c.run(f"config install {fake_url}")

        with patch.object(FileDownloader, 'download', new=download_verify_false):
            c.run(f"config install {fake_url} --insecure")

    @pytest.mark.tool("git")
    def test_git_checkout_is_possible(self):
        folder = self._create_profile_folder()
        c = TestClient(light=True)
        with c.chdir(folder):
            c.run_command('git init .')
            c.run_command('git checkout -b master')
            c.run_command('git add .')
            c.run_command('git config user.name myname')
            c.run_command('git config user.email myname@mycompany.com')
            c.run_command('git commit -m "mymsg"')
            c.run_command('git checkout -b other_branch')
            save(os.path.join(folder, "extensions", "hooks", "cust", "cust.py"), "")
            c.run_command('git add .')
            c.run_command('git commit -m "my file"')

        c.run('config install "%s/.git" --args "-b other_branch"' % folder)
        self._check(c)
        file_path = os.path.join(c.paths.hooks_path, "cust", "cust.py")
        assert load(file_path) == ""

        # Add changes to that branch and update
        with c.chdir(folder):
            save(os.path.join(folder, "extensions", "hooks", "cust", "cust.py"), "new content")
            c.run_command('git add .')
            c.run_command('git commit -m "my other file"')
            c.run_command('git checkout master')
        c.run('config install "%s/.git" --args "-b other_branch"' % folder)
        self._check(c)
        assert load(file_path) == "new content"

    def test_config_install_requester(self):
        # https://github.com/conan-io/conan/issues/4169
        path = self._create_zip()
        c = TestClient(light=True)
        file_server = TestFileServer(os.path.dirname(path))
        c.servers["file_server"] = file_server

        c.run(f"config install {file_server.fake_url}/myconfig.zip")
        assert "Defining remotes from remotes.json" in c.out
        assert "Copying file myfuncs.py" in c.out

    def test_overwrite_read_only_file(self):
        c = TestClient(light=True)
        source_folder = self._create_profile_folder()
        c.run('config install "%s"' % source_folder)
        # make existing settings.yml read-only
        make_file_read_only(c.paths.settings_path)
        assert not os.access(c.paths.settings_path, os.W_OK)

        # config install should overwrite the existing read-only file
        c.run('config install "%s"' % source_folder)
        assert os.access(c.paths.settings_path, os.W_OK)

    def test_dont_copy_file_permissions(self):
        source_folder = self._create_profile_folder()
        # make source settings.yml read-only
        make_file_read_only(os.path.join(source_folder, 'remotes.json'))

        c = TestClient(light=True)
        c.run('config install "%s"' % source_folder)
        assert os.access(c.paths.settings_path, os.W_OK)


class TestConfigInstallSched:

    def test_execute_more_than_once(self):
        """ Once executed by the scheduler, conan config install must executed again
            when invoked manually
        """
        folder = temp_folder(path_with_spaces=False)
        save_files(folder, {"global.conf": "core.download:parallel=0"})
        c = TestClient(light=True)
        c.run('config install "%s"' % folder)
        assert "Copying file global.conf" in c.out

        c.run('config install "%s"' % folder)
        assert "Copying file global.conf" in c.out

    @pytest.mark.tool("git")
    def test_config_install_remove_git_repo(self):
        """ config_install_interval must break when remote git has been removed
        """
        folder = temp_folder(path_with_spaces=False)
        save_files(folder, {"global.conf": "core.download:parallel=0"})
        c = TestClient(light=True)
        with c.chdir(folder):
            c.run_command('git init .')
            c.run_command('git add .')
            c.run_command('git config user.name myname')
            c.run_command('git config user.email myname@mycompany.com')
            c.run_command('git commit -m "mymsg"')
        c.run('config install "%s/.git" --type git' % folder)
        assert "Copying file global.conf" in c.out
        assert "Repo cloned!" in c.out  # git clone executed by scheduled task

    def test_config_fails_git_folder(self):
        # https://github.com/conan-io/conan/issues/8594
        config_folder = temp_folder(path_with_spaces=False)
        save_files(config_folder, {"global.conf": "core.download:parallel=0"})
        folder = os.path.join(temp_folder(), ".gitlab-conan", DEFAULT_CONAN_HOME)
        client = TestClient(cache_folder=folder)
        with client.chdir(config_folder):
            client.run_command('git init .')
            client.run_command('git add .')
            client.run_command('git config user.name myname')
            client.run_command('git config user.email myname@mycompany.com')
            client.run_command('git commit -m "mymsg"')
        assert ".gitlab-conan" in client.cache_folder
        assert os.path.basename(client.cache_folder) == DEFAULT_CONAN_HOME
        client.run('config install "%s/.git" --type git' % config_folder)
        client.load_home("global.conf")  # check it is there
        dirs = os.listdir(client.cache_folder)
        assert ".git" not in dirs


class TestConfigInstall2:
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

    @pytest.fixture(scope="class")
    def servers(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy
            class Conf(ConanFile):
                package_type = "configuration"
                def package(self):
                    copy(self, "*.conf", src=self.build_folder, dst=self.package_folder)
            """)
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": conanfile})
        for pkg in ("myconf_a", "myconf_b", "myconf_c"):
            for version in ("0.1", "0.2"):
                c.save({"global.conf": f"user.myteam:myconf=my_{pkg}/{version}_value"})
                c.run(f"export-pkg . --name={pkg} --version={version}")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c.servers

    @staticmethod
    def _check_conf(c, pkg):
        c.run("config show *")
        assert f"user.myteam:myconf: my_{pkg}_value" in c.out

    @staticmethod
    def _check_conf_file(c, refs):
        content = json.loads(c.load_home("config_version.json"))["config_version"]
        for a, b in zip(refs, content):
            assert a in b

    def test_install_pkg(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_a/0.1")
        self._check_conf_file(c, ["myconf_a/0.1"])
        cache_files = os.listdir(c.cache_folder)
        assert "conaninfo.txt" not in cache_files
        assert "conanmanifest.txt" not in cache_files

        # skip reinstall
        c.run("config install-pkg myconf_a/0.1")
        assert ("The requested configurations are identical to the already installed ones, "
                "skipping re-installation") in c.out
        self._check_conf(c, "myconf_a/0.1")
        self._check_conf_file(c, ["myconf_a/0.1"])

        # forced reinstall
        c.save_home({"global.conf": ""})
        c.run("config install-pkg myconf_a/0.1 --force")
        assert "forcing re-installation because --force" in c.out
        self._check_conf(c, "myconf_a/0.1")
        self._check_conf_file(c, ["myconf_a/0.1"])

    def test_with_url(self, servers):
        c = TestClient(servers=servers, light=True)
        url = servers["default"].fake_url
        c.run("remote remove default")
        c.run(f"config install-pkg myconf_a/0.1 --url={url}")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_a/0.1")
        self._check_conf_file(c, ["myconf_a/0.1"])

    def test_update(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_a/0.2")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_a/0.2")
        self._check_conf_file(c, ["myconf_a/0.2"])

    def test_addition(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_b/0.1")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_b/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

    def test_update_first(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_b/0.1")

        # update of the first fail
        c.run("config install-pkg myconf_a/[*]", assert_error=True)
        assert "ERROR: Installing these configuration packages will break" in c.out
        assert "use 'conan config install-pkg --force' to force" in c.out
        assert "Use 'conan config clean' first to fully reset your configuration" in c.out
        self._check_conf(c, "myconf_b/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        # Now force the first
        c.run("config install-pkg myconf_a/[*] --force")
        assert "Forcing the installation because --force was defined" in c.out
        self._check_conf(c, "myconf_a/0.2")
        self._check_conf_file(c, ["myconf_b/0.1", "myconf_a/0.2"])

    def test_update_second(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_b/0.1")

        # update of the second works without problem
        c.run("config install-pkg myconf_b/[*]")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_b/0.2")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.2"])

    def test_error_cant_use_as_dependency(self):
        c = TestClient(light=True)
        conanfile = GenConanfile("myconf", "0.1").with_package_type("configuration")
        c.save({"myconf/conanfile.py": conanfile,
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("myconf/0.1")})
        c.run("create myconf")
        c.run("install pkg", assert_error=True)
        assert "ERROR: Configuration package myconf/0.1 cannot be used as requirement, " \
               "but pkg/0.1 is requiring it" in c.out

    def test_error_cant_use_without_type(self):
        c = TestClient(light=True)
        c.save({"myconf/conanfile.py": GenConanfile("myconf", "0.1")})
        c.run("create myconf")
        c.run("config install-pkg myconf/[*]", assert_error=True)
        assert 'ERROR: myconf/0.1 is not of package_type="configuration"' in c.out

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

        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": conanfile,
                "global.conf": "user.myteam:myconf=my_myconf/0.1_value"})
        c.run("create .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")

        c.run("config install-pkg myconf/[*]")
        self._check_conf(c, "myconf/0.1")
        self._check_conf_file(c, ["myconf/0.1"])

    def test_lockfile(self, servers):
        """ it should be able to install the config older version using a lockfile
        """
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1 --lockfile-out=config.lock")
        c.run("config install-pkg myconf_a/[*] --lockfile=config.lock")
        assert ("The requested configurations are identical to the already installed ones, "
                "skipping re-installation") in c.out
        self._check_conf(c, "myconf_a/0.1")
        self._check_conf_file(c, ["myconf_a/0.1"])

        # Without the lockfile, it is free to update
        c.run("config install-pkg myconf_a/[*] --lockfile-out=config.lock")
        assert "Installing new or updating configuration packages"
        self._check_conf(c, "myconf_a/0.2")
        self._check_conf_file(c, ["myconf_a/0.2"])
        result = json.loads(c.load("config.lock"))
        assert "myconf_a/0.2" in result["config_requires"][0]

    def test_install_from_file(self, servers):
        c = TestClient(servers=servers, light=True)
        # To make explicit the format of the conanconfig file
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/0.1
                - myconf_b/0.1
            """)
        c.save({"conanconfig.yml": conanconfig})
        # Admits the default location .
        c.run("config install-pkg")
        self._check_conf(c, "myconf_b/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        # install same file again:
        c.run("config install-pkg .")
        assert ("The requested configurations are identical to the already installed ones, "
                "skipping re-installation") in c.out
        self._check_conf(c, "myconf_b/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        # Forced re-install
        c.save_home({"global.conf": ""})
        c.run("config install-pkg . --force")
        assert "forcing re-installation because --force" in c.out
        self._check_conf(c, "myconf_b/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

    def test_install_from_file_with_url(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("remote remove default")
        server_url = servers["default"].fake_url
        conanconfig = yaml.dump({"packages": ["myconf_a/0.1"], "urls": [server_url]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        self._check_conf(c, "myconf_a/0.1")
        self._check_conf_file(c, ["myconf_a/0.1"])

    def test_update_with_file(self, servers):
        c = TestClient(servers=servers, light=True)
        conanconfig = yaml.dump({"packages": ["myconf_a/0.1", "myconf_b/0.1"]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")

        # Now installing "updates" without disrupting the order
        c.run("config install-pkg myconf_c/0.1")
        assert "Installing new or updating configuration packages"
        self._check_conf(c, "myconf_c/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1", "myconf_c/0.1"])

        # Now installing "updates" without disrupting the order
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/0.1
                - myconf_b/0.1
                - myconf_c/[*]
            """)
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_c/0.2")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1", "myconf_c/0.2"])

        # This is also an update of the existing ones, keeping the order
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/[*]
                - myconf_b/0.1
                - myconf_c/[*]
            """)
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        assert "Installing new or updating configuration packages" in c.out
        self._check_conf(c, "myconf_c/0.2")
        self._check_conf_file(c, ["myconf_a/0.2", "myconf_b/0.1", "myconf_c/0.2"])

    def test_failed_update_force(self, servers):
        c = TestClient(servers=servers, light=True)
        conanconfig = yaml.dump({"packages": ["myconf_a/0.1", "myconf_b/0.1"]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")

        # Now installing "updates" without disrupting the order
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/0.2
            """)
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .", assert_error=True)
        assert "use 'conan config install-pkg --force' to force" in c.out
        assert "Use 'conan config clean' first to fully reset" in c.out
        self._check_conf(c, "myconf_b/0.1")
        self._check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        c.run("config install-pkg . --force")
        assert "Forcing the installation because --force was defined" in c.out
        self._check_conf(c, "myconf_a/0.2")
        self._check_conf_file(c, ["myconf_b/0.1", "myconf_a/0.2"])

    def test_install_from_file_with_lockfile(self, servers):
        # it should stay in version 0.1
        c = TestClient(servers=servers)
        c.run("config install-pkg myconf_a/0.1 --lockfile-out=conan.lock")
        conanconfig = yaml.dump({"packages": ["myconf_a/[>=0.1 <1.0]"]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        path = HomePaths(c.cache_folder).config_version_path
        # First are the newest installed
        configs = json.loads(load(path))["config_version"]
        configs = [str(RecipeReference.loads(r)) for r in configs]
        assert configs == ["myconf_a/0.1"]


class TestConfigInstallPkgSettings:
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Conf(ConanFile):
            name = "myconf"
            version = "0.1"
            settings = "os"
            package_type = "configuration"
            def package(self):
                f = "win" if self.settings.os == "Windows" else "nix"
                copy(self, "*.conf", src=os.path.join(self.build_folder, f), dst=self.package_folder)
            """)

    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "win/global.conf": "user.myteam:myconf=mywinvalue",
                "nix/global.conf": "user.myteam:myconf=mynixvalue",
                })
        c.run("export-pkg . -s os=Windows")
        c.run("export-pkg . -s os=Linux")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c

    @pytest.mark.parametrize("default_profile", [False, True])
    def test_config_install_from_pkg(self, client, default_profile):
        # Now install it
        c = client
        if not default_profile:
            os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*] -s os=Windows")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mywinvalue" in c.out

        c.run("config install-pkg myconf/[*] -s os=Linux --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mynixvalue" in c.out

    def test_error_no_settings_defined(self, client):
        c = client
        os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*]", assert_error=True)
        assert "There are invalid packages:" in c.out
        assert "myconf/0.1: Invalid: 'settings.os' value not defined" in c.out

    def test_config_install_from_pkg_profile(self, client):
        # Now install it
        c = client
        c.save({"win.profile": "[settings]\nos=Windows",
                "nix.profile": "[settings]\nos=Linux"})
        c.run("config install-pkg myconf/[*] -pr=win.profile")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mywinvalue" in c.out

        c.run("config install-pkg myconf/[*] -pr=nix.profile --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mynixvalue" in c.out

    def test_config_install_from_pkg_profile_default(self, client):
        # Now install it
        c = client
        c.save_home({"profiles/default": "[settings]\nos=Windows"})
        c.run("config install-pkg myconf/[*]")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mywinvalue" in c.out

        c.save_home({"profiles/default": "[settings]\nos=Linux"})
        c.run("config install-pkg myconf/[*] --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mynixvalue" in c.out


class TestConfigInstallPkgOptions:
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Conf(ConanFile):
            name = "myconf"
            version = "0.1"
            options = {"project": ["project1", "project2"]}
            default_options = {"project": "project1"}
            package_type = "configuration"
            def package(self):
                copy(self, "*.conf", src=os.path.join(self.build_folder, str(self.options.project)),
                     dst=self.package_folder)
            """)

    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "project1/global.conf": "user.myteam:myconf=my1value",
                "project2/global.conf": "user.myteam:myconf=my2value",
                })
        c.run("export-pkg .")
        c.run("export-pkg . -o project=project2")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c

    @pytest.mark.parametrize("default_profile", [False, True])
    def test_config_install_from_pkg(self, client, default_profile):
        # Now install it
        c = client
        if not default_profile:
            os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*] -o &:project=project1")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

        c.run("config install-pkg myconf/[*] -o &:project=project2 --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my2value" in c.out

    def test_no_option_defined(self, client):
        c = client
        os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*]")
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

    def test_config_install_from_pkg_profile(self, client):
        # Now install it
        c = client
        c.save({"win.profile": "[options]\n&:project=project1",
                "nix.profile": "[options]\n&:project=project2"})
        c.run("config install-pkg myconf/[*] -pr=win.profile")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

        c.run("config install-pkg myconf/[*] -pr=nix.profile --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my2value" in c.out

    def test_config_install_from_pkg_profile_default(self, client):
        # Now install it
        c = client
        c.save_home({"profiles/default": "[options]\n&:project=project1"})
        c.run("config install-pkg myconf/[*]")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

        c.save_home({"profiles/default": "[options]\n&:project=project2"})
        c.run("config install-pkg myconf/[*] --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my2value" in c.out
