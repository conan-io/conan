# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import sys
import unittest
from collections import namedtuple

import pytest
import requests
import six
from bottle import request, static_file, HTTPError
from mock.mock import mock_open, patch
from parameterized import parameterized
from requests.models import Response

from conans.client import tools
from conans.client.cache.cache import CONAN_CONF
from conans.client.conan_api import ConanAPIV1
from conans.client.conf import get_default_client_conf
from conans.client.output import ConanOutput
from conans.client.tools import chdir
from conans.client.tools.files import replace_in_file
from conans.client.tools.oss import OSInfo
from conans.client.tools.win import vswhere
from conans.errors import ConanException, AuthenticationException
from conans.model.build_info import CppInfo
from conans.test.utils.mocks import ConanFileMock, TestBufferConanOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import StoppableThreadBottle, TestClient, zipdir
from conans.tools import get_global_instances
from conans.util.files import load, md5, mkdir, save
from conans.util.runners import check_output_runner


class ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class RunnerMock(object):
    def __init__(self, return_ok=True, output=None):
        self.command_called = None
        self.return_ok = return_ok
        self.output = output

    def __call__(self, command, output, win_bash=False, subsystem=None):  # @UnusedVariable
        self.command_called = command
        self.win_bash = win_bash
        self.subsystem = subsystem
        if self.output and output and hasattr(output, "write"):
            output.write(self.output)
        return 0 if self.return_ok else 1


class ReplaceInFileTest(unittest.TestCase):
    def setUp(self):
        text = u'J\xe2nis\xa7'
        self.tmp_folder = temp_folder()

        self.win_file = os.path.join(self.tmp_folder, "win_encoding.txt")
        text = text.encode("Windows-1252", "ignore")
        with open(self.win_file, "wb") as handler:
            handler.write(text)

        self.bytes_file = os.path.join(self.tmp_folder, "bytes_encoding.txt")
        with open(self.bytes_file, "wb") as handler:
            handler.write(text)

    def test_replace_in_file(self):
        output = ConanOutput(sys.stdout)
        replace_in_file(self.win_file, "nis", "nus", output=output)
        replace_in_file(self.bytes_file, "nis", "nus", output=output)

        content = tools.load(self.win_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)

        content = tools.load(self.bytes_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)


class ToolsTest(unittest.TestCase):
    output = TestBufferConanOutput()

    def test_replace_paths(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        replace_with = "MYPATH"
        expected = 'Some other contentsMYPATH"finally all text'

        out = TestBufferConanOutput()
        save(path, 'Some other contentsc:\\Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/Path/to/file.txt", replace_with,
                                         windows_paths=True, output=out)
        self.assertEqual(load(path), expected)
        self.assertTrue(ret)

        save(path, 'Some other contentsC:/Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/PATH/to/FILE.txt", replace_with,
                                         windows_paths=True, output=out)
        self.assertEqual(load(path), expected)
        self.assertTrue(ret)

        save(path, 'Some other contentsD:/Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/PATH/to/FILE.txt", replace_with, strict=False,
                                         windows_paths=True, output=out)
        self.assertEqual(load(path), 'Some other contentsD:/Path\\TO\\file.txt"finally all text')
        self.assertFalse(ret)

        # Multiple matches
        s = 'Some other contentsD:/Path\\TO\\file.txt"finally all textd:\\PATH\\to\\file.TXTMoretext'
        save(path, s)
        ret = tools.replace_path_in_file(path, "D:/PATH/to/FILE.txt", replace_with, strict=False,
                                         windows_paths=True, output=out)
        self.assertEqual(load(path), 'Some other contentsMYPATH"finally all textMYPATHMoretext')
        self.assertTrue(ret)

        # Automatic windows_paths
        save(path, s)
        ret = tools.replace_path_in_file(path, "D:/PATH/to/FILE.txt", replace_with, strict=False,
                                         output=out)
        if platform.system() == "Windows":
            self.assertEqual(load(path), 'Some other contentsMYPATH"finally all textMYPATHMoretext')
            self.assertTrue(ret)
        else:
            self.assertFalse(ret)

    def test_load_save(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        save(path, u"äüïöñç")
        content = load(path)
        self.assertEqual(content, u"äüïöñç")

    def test_md5(self):
        result = md5(u"äüïöñç")
        self.assertEqual("dfcc3d74aa447280a7ecfdb98da55174", result)

    def test_cpu_count(self):
        output = ConanOutput(sys.stdout)
        cpus = tools.cpu_count(output=output)
        self.assertIsInstance(cpus, int)
        self.assertGreaterEqual(cpus, 1)
        with tools.environment_append({"CONAN_CPU_COUNT": "34"}):
            self.assertEqual(tools.cpu_count(output=output), 34)
        with tools.environment_append({"CONAN_CPU_COUNT": "null"}):
            with six.assertRaisesRegex(self, ConanException, "Invalid CONAN_CPU_COUNT value"):
                tools.cpu_count(output=output)

    @patch("conans.client.tools.oss.CpuProperties.get_cpu_period")
    @patch("conans.client.tools.oss.CpuProperties.get_cpu_quota")
    def test_cpu_count_in_container(self, get_cpu_quota_mock, get_cpu_period_mock):
        get_cpu_quota_mock.return_value = 12000
        get_cpu_period_mock.return_value = 1000

        output = ConanOutput(sys.stdout)
        cpus = tools.cpu_count(output=output)
        self.assertEqual(12, cpus)

    def test_get_env_unit(self):
        """
        Unit tests tools.get_env
        """
        # Test default
        self.assertIsNone(
            tools.get_env("NOT_DEFINED", environment={}),
            None
        )
        # Test defined default
        self.assertEqual(
            tools.get_env("NOT_DEFINED_KEY", default="random_default", environment={}),
            "random_default"
        )
        # Test return defined string
        self.assertEqual(
            tools.get_env("FROM_STR", default="", environment={"FROM_STR": "test_string_value"}),
            "test_string_value"
        )
        # Test boolean conversion
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "1"}),
            True
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": "0"}),
            False
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "True"}),
            True
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": ""}),
            False
        )
        # Test int conversion
        self.assertEqual(
            tools.get_env("TO_INT", default=2, environment={"TO_INT": "1"}),
            1
        )
        # Test float conversion
        self.assertEqual(
            tools.get_env("TO_FLOAT", default=2.0, environment={"TO_FLOAT": "1"}),
            1.0
        ),
        # Test list conversion
        self.assertEqual(
            tools.get_env("TO_LIST", default=[], environment={"TO_LIST": "1,2,3"}),
            ["1", "2", "3"]
        )
        self.assertEqual(
            tools.get_env("TO_LIST_NOT_TRIMMED", default=[], environment={"TO_LIST_NOT_TRIMMED":
                                                                          " 1 , 2 , 3 "}),
            ["1", "2", "3"]
        )

    def test_get_env_in_conanfile(self):
        """
        Test get_env is available and working in conanfile
        """
        client = TestClient()

        conanfile = """from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        run_tests = tools.get_env("CONAN_RUN_TESTS", default=False)
        print("test_get_env_in_conafile CONAN_RUN_TESTS=%r" % run_tests)
        assert(run_tests == True)
        """
        client.save({"conanfile.py": conanfile})

        with tools.environment_append({"CONAN_RUN_TESTS": "1"}):
            client.run("install .")
            client.run("build .")

    def test_global_tools_overrided(self):
        client = TestClient()

        conanfile = """
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        assert(tools._global_requester != None)
        assert(tools._global_output != None)
        """
        client.save({"conanfile.py": conanfile})

        client.run("install .")
        client.run("build .")

        # Not test the real commmand get_command if it's setting the module global vars
        tmp = temp_folder()
        conf = get_default_client_conf().replace("\n[proxies]", "\n[proxies]\nhttp = http://myproxy.com")
        os.mkdir(os.path.join(tmp, ".conan"))
        save(os.path.join(tmp, ".conan", CONAN_CONF), conf)
        with tools.environment_append({"CONAN_USER_HOME": tmp}):
            conan_api, _, _ = ConanAPIV1.factory()
        conan_api.remote_list()
        global_output, global_requester = get_global_instances()
        self.assertEqual(global_requester.proxies, {"http": "http://myproxy.com"})
        self.assertIsNotNone(global_output.warn)

    def test_environment_nested(self):
        with tools.environment_append({"A": "1", "Z": "40"}):
            with tools.environment_append({"A": "1", "B": "2"}):
                with tools.environment_append({"A": "2", "B": "2"}):
                    self.assertEqual(os.getenv("A"), "2")
                    self.assertEqual(os.getenv("B"), "2")
                    self.assertEqual(os.getenv("Z"), "40")
                self.assertEqual(os.getenv("A", None), "1")
                self.assertEqual(os.getenv("B", None), "2")
            self.assertEqual(os.getenv("A", None), "1")
            self.assertEqual(os.getenv("Z", None), "40")

        self.assertEqual(os.getenv("A", None), None)
        self.assertEqual(os.getenv("B", None), None)
        self.assertEqual(os.getenv("Z", None), None)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires vswhere")
    def test_vswhere_description_strip(self):
        myoutput = """
[
  {
    "instanceId": "17609d7c",
    "installDate": "2018-06-11T02:15:04Z",
    "installationName": "VisualStudio/15.7.3+27703.2026",
    "installationPath": "",
    "installationVersion": "15.7.27703.2026",
    "productId": "Microsoft.VisualStudio.Product.Enterprise",
    "productPath": "",
    "isPrerelease": false,
    "displayName": "Visual Studio Enterprise 2017",
    "description": "生産性向上と、さまざまな規模のチーム間の調整のための Microsoft DevOps ソリューション",
    "channelId": "VisualStudio.15.Release",
    "channelUri": "https://aka.ms/vs/15/release/channel",
    "enginePath": "",
    "releaseNotes": "https://go.microsoft.com/fwlink/?LinkId=660692#15.7.3",
    "thirdPartyNotices": "https://go.microsoft.com/fwlink/?LinkId=660708",
    "updateDate": "2018-06-11T02:15:04.7009868Z",
    "catalog": {
      "buildBranch": "d15.7",
      "buildVersion": "15.7.27703.2026",
      "id": "VisualStudio/15.7.3+27703.2026",
      "localBuild": "build-lab",
      "manifestName": "VisualStudio",
      "manifestType": "installer",
      "productDisplayVersion": "15.7.3",
      "productLine": "Dev15",
      "productLineVersion": "2017",
      "productMilestone": "RTW",
      "productMilestoneIsPreRelease": "False",
      "productName": "Visual Studio",
      "productPatchVersion": "3",
      "productPreReleaseMilestoneSuffix": "1.0",
      "productRelease": "RTW",
      "productSemanticVersion": "15.7.3+27703.2026",
      "requiredEngineVersion": "1.16.1187.57215"
    },
    "properties": {
      "campaignId": "",
      "canceled": "0",
      "channelManifestId": "VisualStudio.15.Release/15.7.3+27703.2026",
      "nickname": "",
      "setupEngineFilePath": ""
    }
  },
  {
    "instanceId": "VisualStudio.12.0",
    "installationPath": "",
    "installationVersion": "12.0"
  }
]

"""
        if six.PY3:
            # In python3 the output from subprocess.check_output are bytes, not str
            myoutput = myoutput.encode()
        myrunner = mock_open()
        myrunner.check_output = lambda x: myoutput
        with patch('conans.client.tools.win.subprocess', myrunner):
            json = vswhere()
            self.assertNotIn("descripton", json)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_run_in_bash(self):

        class MockConanfile(object):
            def __init__(self):

                self.output = namedtuple("output", "info")(lambda x: None)  # @UnusedVariable
                self.env = {"PATH": "/path/to/somewhere"}

                class MyRun(object):
                    def __call__(self, command, output, log_filepath=None,
                                 cwd=None, subprocess=False):  # @UnusedVariable
                        self.command = command
                self._conan_runner = MyRun()

        conanfile = MockConanfile()
        with patch.object(OSInfo, "bash_path", return_value='bash'):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn("bash", conanfile._conan_runner.command)
            self.assertIn("--login -c", conanfile._conan_runner.command)
            self.assertIn("^&^& a_command.bat ^", conanfile._conan_runner.command)

        with tools.environment_append({"CONAN_BASH_PATH": "path\\to\\mybash.exe"}):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn('path\\to\\mybash.exe --login -c', conanfile._conan_runner.command)

        with tools.environment_append({"CONAN_BASH_PATH": "path with spaces\\to\\mybash.exe"}):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin",
                                      with_login=False)
            self.assertIn('"path with spaces\\to\\mybash.exe"  -c', conanfile._conan_runner.command)

        # try to append more env vars
        conanfile = MockConanfile()
        with patch.object(OSInfo, "bash_path", return_value='bash'):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin",
                                      env={"PATH": "/other/path", "MYVAR": "34"})
            self.assertIn('^&^& PATH=\\^"/other/path:/path/to/somewhere:$PATH\\^" '
                          '^&^& MYVAR=34 ^&^& a_command.bat ^', conanfile._conan_runner.command)

    def test_download_retries_errors(self):
        out = TestBufferConanOutput()

        # Retry arguments override defaults
        with six.assertRaisesRegex(self, ConanException, "Error downloading"):
            tools.download("http://fakeurl3.es/nonexists",
                           os.path.join(temp_folder(), "file.txt"), out=out,
                           requester=requests,
                           retry=2, retry_wait=1)
        self.assertEqual(str(out).count("Waiting 1 seconds to retry..."), 2)

        # Not found error
        with six.assertRaisesRegex(self, ConanException,
                                   "Not found: http://google.es/FILE_NOT_FOUND"):
            tools.download("http://google.es/FILE_NOT_FOUND",
                           os.path.join(temp_folder(), "README.txt"), out=out,
                           requester=requests,
                           retry=2, retry_wait=0)

    @pytest.mark.slow
    def test_download_retries(self):
        http_server = StoppableThreadBottle()

        with tools.chdir(tools.mkdir_tmp()):
            with open("manual.html", "w") as fmanual:
                fmanual.write("this is some content")
                manual_file = os.path.abspath("manual.html")

        from bottle import auth_basic

        @http_server.server.get("/manual.html")
        def get_manual():
            return static_file(os.path.basename(manual_file),
                               os.path.dirname(manual_file))

        def check_auth(user, password):
            # Check user/password here
            return user == "user" and password == "passwd"

        @http_server.server.get('/basic-auth/<user>/<password>')
        @auth_basic(check_auth)
        def get_manual_auth(user, password):
            return static_file(os.path.basename(manual_file),
                               os.path.dirname(manual_file))

        http_server.run_server()

        out = TestBufferConanOutput()

        dest = os.path.join(temp_folder(), "manual.html")
        tools.download("http://localhost:%s/manual.html" % http_server.port, dest, out=out, retry=3,
                       retry_wait=0, requester=requests)
        self.assertTrue(os.path.exists(dest))
        content = load(dest)

        # overwrite = False
        with self.assertRaises(ConanException):
            tools.download("http://localhost:%s/manual.html" % http_server.port, dest, out=out,
                           retry=2, retry_wait=0, overwrite=False, requester=requests)

        # overwrite = True
        tools.download("http://localhost:%s/manual.html" % http_server.port, dest, out=out, retry=2,
                       retry_wait=0, overwrite=True, requester=requests)
        self.assertTrue(os.path.exists(dest))
        content_new = load(dest)
        self.assertEqual(content, content_new)

        # Not authorized
        with self.assertRaises(ConanException):
            tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                           overwrite=True, requester=requests, out=out, retry=0, retry_wait=0)

        # Authorized
        tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                       auth=("user", "passwd"), overwrite=True, requester=requests, out=out,
                       retry=0, retry_wait=0)

        # Authorized using headers
        tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                       headers={"Authorization": "Basic dXNlcjpwYXNzd2Q="}, overwrite=True,
                       requester=requests, out=out, retry=0, retry_wait=0)
        http_server.stop()

    @pytest.mark.slow
    @patch("conans.tools._global_config")
    def test_download_unathorized(self, mock_config):
        http_server = StoppableThreadBottle()
        mock_config.return_value = ConfigMock()

        @http_server.server.get('/forbidden')
        def get_forbidden():
            return HTTPError(403, "Access denied.")

        http_server.run_server()

        out = TestBufferConanOutput()
        dest = os.path.join(temp_folder(), "manual.html")
        # Not authorized
        with six.assertRaisesRegex(self, AuthenticationException, "403"):
            tools.download("http://localhost:%s/forbidden" % http_server.port, dest,
                           requester=requests, out=out)

        http_server.stop()

    @parameterized.expand([
        ["Linux", "x86", None, "x86-linux-gnu"],
        ["Linux", "x86_64", None, "x86_64-linux-gnu"],
        ["Linux", "armv6", None, "arm-linux-gnueabi"],
        ["Linux", "sparc", None, "sparc-linux-gnu"],
        ["Linux", "sparcv9", None, "sparc64-linux-gnu"],
        ["Linux", "mips", None, "mips-linux-gnu"],
        ["Linux", "mips64", None, "mips64-linux-gnu"],
        ["Linux", "ppc32", None, "powerpc-linux-gnu"],
        ["Linux", "ppc64", None, "powerpc64-linux-gnu"],
        ["Linux", "ppc64le", None, "powerpc64le-linux-gnu"],
        ["Linux", "armv5te", None, "arm-linux-gnueabi"],
        ["Linux", "arm_whatever", None, "arm-linux-gnueabi"],
        ["Linux", "armv7hf", None, "arm-linux-gnueabihf"],
        ["Linux", "armv6", None, "arm-linux-gnueabi"],
        ["Linux", "armv7", None, "arm-linux-gnueabi"],
        ["Linux", "armv8_32", None, "aarch64-linux-gnu_ilp32"],
        ["Linux", "armv5el", None, "arm-linux-gnueabi"],
        ["Linux", "armv5hf", None, "arm-linux-gnueabihf"],
        ["Linux", "s390", None, "s390-ibm-linux-gnu"],
        ["Linux", "s390x", None, "s390x-ibm-linux-gnu"],
        ["Android", "x86", None, "i686-linux-android"],
        ["Android", "x86_64", None, "x86_64-linux-android"],
        ["Android", "armv6", None, "arm-linux-androideabi"],
        ["Android", "armv7", None, "arm-linux-androideabi"],
        ["Android", "armv7hf", None, "arm-linux-androideabi"],
        ["Android", "armv8", None, "aarch64-linux-android"],
        ["Windows", "x86", "Visual Studio", "i686-windows-msvc"],
        ["Windows", "x86", "gcc", "i686-w64-mingw32"],
        ["Windows", "x86_64", "gcc", "x86_64-w64-mingw32"],
        ["Darwin", "x86_64", None, "x86_64-apple-darwin"],
        ["Macos", "x86", None, "i686-apple-darwin"],
        ["iOS", "armv7", None, "arm-apple-ios"],
        ["iOS", "x86", None, "i686-apple-ios"],
        ["iOS", "x86_64", None, "x86_64-apple-ios"],
        ["watchOS", "armv7k", None, "arm-apple-watchos"],
        ["watchOS", "armv8_32", None, "aarch64-apple-watchos"],
        ["watchOS", "x86", None, "i686-apple-watchos"],
        ["watchOS", "x86_64", None, "x86_64-apple-watchos"],
        ["tvOS", "armv8", None, "aarch64-apple-tvos"],
        ["tvOS", "armv8.3", None, "aarch64-apple-tvos"],
        ["tvOS", "x86", None, "i686-apple-tvos"],
        ["tvOS", "x86_64", None, "x86_64-apple-tvos"],
        ["Emscripten", "asm.js", None, "asmjs-local-emscripten"],
        ["Emscripten", "wasm", None, "wasm32-local-emscripten"],
        ["AIX", "ppc32", None, "rs6000-ibm-aix"],
        ["AIX", "ppc64", None, "powerpc-ibm-aix"],
        ["Neutrino", "armv7", None, "arm-nto-qnx"],
        ["Neutrino", "armv8", None, "aarch64-nto-qnx"],
        ["Neutrino", "sh4le", None, "sh4-nto-qnx"],
        ["Neutrino", "ppc32be", None, "powerpcbe-nto-qnx"],
        ["Linux", "e2k-v2", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v3", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v4", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v5", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v6", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v7", None, "e2k-unknown-linux-gnu"],
    ])
    def test_get_gnu_triplet(self, os, arch, compiler, expected_triplet):
        triplet = tools.get_gnu_triplet(os, arch, compiler)
        self.assertEqual(triplet, expected_triplet,
                         "triplet did not match for ('%s', '%s', '%s')" % (os, arch, compiler))

    def test_get_gnu_triplet_on_windows_without_compiler(self):
        with self.assertRaises(ConanException):
            tools.get_gnu_triplet("Windows", "x86")

    def test_detect_windows_subsystem(self):
        # Don't raise test
        result = OSInfo.detect_windows_subsystem()
        if not OSInfo.bash_path() or platform.system() != "Windows":
            self.assertEqual(None, result)
        else:
            self.assertEqual(str, type(result))

    @pytest.mark.slow
    @pytest.mark.local_bottle
    def test_get_filename_download(self):
        # Create a tar file to be downloaded from server
        with tools.chdir(tools.mkdir_tmp()):
            import tarfile
            tar_file = tarfile.open("sample.tar.gz", "w:gz")
            mkdir("test_folder")
            tar_file.add(os.path.abspath("test_folder"), "test_folder")
            tar_file.close()
            file_path = os.path.abspath("sample.tar.gz")
            assert(os.path.exists(file_path))

        # Instance stoppable thread server and add endpoints
        thread = StoppableThreadBottle()

        @thread.server.get("/this_is_not_the_file_name")
        def get_file():
            return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

        @thread.server.get("/")
        def get_file2():
            self.assertEqual(request.query["file"], "1")
            return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

        @thread.server.get("/error_url")
        def error_url():
            from bottle import response
            response.status = 500
            return 'This always fail'

        thread.run_server()

        out = TestBufferConanOutput()
        # Test: File name cannot be deduced from '?file=1'
        with self.assertRaises(ConanException) as error:
            tools.get("http://localhost:%s/?file=1" % thread.port, output=out)
        self.assertIn("Cannot deduce file name from the url: 'http://localhost:{}/?file=1'."
                      " Use 'filename' parameter.".format(thread.port), str(error.exception))

        # Test: Works with filename parameter instead of '?file=1'
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/?file=1" % thread.port, filename="sample.tar.gz",
                      requester=requests, output=out, retry=0, retry_wait=0)
            self.assertTrue(os.path.exists("test_folder"))

        # Test: Use a different endpoint but still not the filename one
        with tools.chdir(tools.mkdir_tmp()):
            from zipfile import BadZipfile
            with self.assertRaises(BadZipfile):
                tools.get("http://localhost:%s/this_is_not_the_file_name" % thread.port,
                          requester=requests, output=out, retry=0, retry_wait=0)
            tools.get("http://localhost:%s/this_is_not_the_file_name" % thread.port,
                      filename="sample.tar.gz", requester=requests, output=out,
                      retry=0, retry_wait=0)
            self.assertTrue(os.path.exists("test_folder"))
        thread.stop()

        with six.assertRaisesRegex(self, ConanException, "Error"):
            tools.get("http://localhost:%s/error_url" % thread.port,
                      filename="fake_sample.tar.gz", requester=requests, output=out, verify=False,
                      retry=2, retry_wait=0)

        # Not found error
        self.assertEqual(str(out).count("Waiting 0 seconds to retry..."), 2)

    def test_get_unzip_strip_root(self):
        """Test that the strip_root mechanism from the underlying unzip
          is called if I call the tools.get by checking that the exception of an invalid zip to
          flat is raised"""

        zip_folder = temp_folder()

        def mock_download(*args, **kwargs):
            tmp_folder = temp_folder()
            with chdir(tmp_folder):
                ori_files_dir = os.path.join(tmp_folder, "subfolder-1.2.3")
                file1 = os.path.join(ori_files_dir, "file1")
                file2 = os.path.join(ori_files_dir, "folder", "file2")
                # !!! This file is not under the root "subfolder-1.2.3"
                file3 = os.path.join("file3")
                save(file1, "")
                save(file2, "")
                save(file3, "")
                zip_file = os.path.join(zip_folder, "file.zip")
                zipdir(tmp_folder, zip_file)

        with six.assertRaisesRegex(self, ConanException, "The zip file contains more than 1 "
                                                         "folder in the root"):
            with patch('conans.client.tools.net.download', new=mock_download):
                with chdir(zip_folder):
                    tools.get("file.zip", strip_root=True)

    @pytest.mark.slow
    @pytest.mark.local_bottle
    def test_get_gunzip(self):
        # Create a tar file to be downloaded from server
        tmp = temp_folder()
        filepath = os.path.join(tmp, "test.txt.gz")
        import gzip
        with gzip.open(filepath, "wb") as f:
            f.write(b"hello world zipped!")

        thread = StoppableThreadBottle()

        @thread.server.get("/test.txt.gz")
        def get_file():
            return static_file(os.path.basename(filepath), root=os.path.dirname(filepath),
                               mimetype="application/octet-stream")

        thread.run_server()

        out = TestBufferConanOutput()
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/test.txt.gz" % thread.port, requester=requests,
                      output=out, retry=0, retry_wait=0)
            self.assertTrue(os.path.exists("test.txt"))
            self.assertEqual(load("test.txt"), "hello world zipped!")
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/test.txt.gz" % thread.port, requester=requests,
                      output=out, destination="myfile.doc", retry=0, retry_wait=0)
            self.assertTrue(os.path.exists("myfile.doc"))
            self.assertEqual(load("myfile.doc"), "hello world zipped!")
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/test.txt.gz" % thread.port, requester=requests,
                      output=out, destination="mytemp/myfile.txt", retry=0, retry_wait=0)
            self.assertTrue(os.path.exists("mytemp/myfile.txt"))
            self.assertEqual(load("mytemp/myfile.txt"), "hello world zipped!")

        thread.stop()

    @patch("conans.client.tools.net.unzip")
    def test_get_mirror(self, _):
        """ tools.get must supports a list of URLs. However, only one must be downloaded.
        """

        class MockRequester(object):
            def __init__(self):
                self.count = 0
                self.fail_first = False
                self.fail_all = False

            def get(self, *args, **kwargs):
                self.count += 1
                resp = Response()
                resp._content = b'{"results": []}'
                resp.headers = {"Content-Type": "application/json"}
                resp.status_code = 200
                if (self.fail_first and self.count == 1) or self.fail_all:
                    resp.status_code = 408
                return resp

        file = "test.txt.gz"
        out = TestBufferConanOutput()
        urls = ["http://localhost:{}/{}".format(8000 + i, file) for i in range(3)]

        # Only the first file must be downloaded
        with tools.chdir(tools.mkdir_tmp()):
            requester = MockRequester()
            tools.get(urls, requester=requester, output=out, retry=0, retry_wait=0)
            self.assertEqual(1, requester.count)

        # Fail the first, download only the second
        with tools.chdir(tools.mkdir_tmp()):
            requester = MockRequester()
            requester.fail_first = True
            tools.get(urls, requester=requester, output=out, retry=0, retry_wait=0)
            self.assertEqual(2, requester.count)
            self.assertIn("WARN: Could not download from the URL {}: Error 408 downloading file {}."
                          " Trying another mirror."
                          .format(urls[0], urls[0]), out)

        # Fail all downloads
        with tools.chdir(tools.mkdir_tmp()):
            requester = MockRequester()
            requester.fail_all = True
            with self.assertRaises(ConanException) as error:
                tools.get(urls, requester=requester, output=out, retry=0, retry_wait=0)
            self.assertEqual(3, requester.count)
            self.assertIn("All downloads from (3) URLs have failed.", str(error.exception))

    def test_check_output_runner(self):
        original_temp = temp_folder()
        patched_temp = os.path.join(original_temp, "dir with spaces")
        payload = "hello world"
        output = check_output_runner(["echo", payload], stderr=subprocess.STDOUT)
        self.assertIn(payload, str(output))

    def test_unix_to_dos_conanfile(self):
        client = TestClient()
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "file.txt"

    def build(self):
        assert("\\r\\n" in tools.load("file.txt"))
        tools.dos2unix("file.txt")
        assert("\\r\\n" not in tools.load("file.txt"))
        tools.unix2dos("file.txt")
        assert("\\r\\n" in tools.load("file.txt"))
"""
        client.save({"conanfile.py": conanfile, "file.txt": "hello\r\n"})
        client.run("create . user/channel")


class CollectLibTestCase(unittest.TestCase):

    def test_collect_libs(self):
        conanfile = ConanFileMock()
        # Without package_folder
        result = tools.collect_libs(conanfile)
        self.assertEqual([], result)

        # Default behavior
        conanfile.folders.set_base_package(temp_folder())
        mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(mylib_path, "")
        conanfile.cpp_info = CppInfo("", "")
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)

        # Custom folder
        customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
        save(customlib_path, "")
        result = tools.collect_libs(conanfile, folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Custom folder doesn't exist
        result = tools.collect_libs(conanfile, folder="fake_folder")
        self.assertEqual([], result)
        self.assertIn("Lib folder doesn't exist, can't collect libraries:", conanfile.output)

        # Use cpp_info.libdirs
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = tools.collect_libs(conanfile)
        self.assertEqual(["customlib", "mylib"], result)

        # Custom folder with multiple libdirs should only collect from custom folder
        self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
        result = tools.collect_libs(conanfile, folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Unicity of lib names
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo(conanfile.name, "")
        custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(custom_mylib_path, "")
        save(lib_mylib_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)

        # Warn lib folder does not exist with correct result
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo(conanfile.name, "")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(lib_mylib_path, "")
        no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
        conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)
        self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                      % no_folder_path, conanfile.output)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Needs symlinks support")
    def test_collect_libs_symlinks(self):
        # Keep only the shortest lib name per group of symlinks
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo(conanfile.name, "")
        version_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.1.0.0.dylib")
        soversion_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.1.dylib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.dylib")
        lib_mylib2_path = os.path.join(conanfile.package_folder, "lib", "libmylib.2.dylib")
        lib_mylib3_path = os.path.join(conanfile.package_folder, "custom_folder", "libmylib.3.dylib")
        save(version_mylib_path, "")
        os.symlink(version_mylib_path, soversion_mylib_path)
        os.symlink(soversion_mylib_path, lib_mylib_path)
        save(lib_mylib2_path, "")
        save(lib_mylib3_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib", "mylib.2", "mylib.3"], result)

    def test_self_collect_libs(self):
        conanfile = ConanFileMock()
        # Without package_folder
        result = conanfile.collect_libs()
        self.assertEqual([], result)

        # Default behavior
        conanfile.folders.set_base_package(temp_folder())
        mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(mylib_path, "")
        conanfile.cpp_info = CppInfo("", "")
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)

        # Custom folder
        customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
        save(customlib_path, "")
        result = conanfile.collect_libs(folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Custom folder doesn't exist
        result = conanfile.collect_libs(folder="fake_folder")
        self.assertEqual([], result)
        self.assertIn("Lib folder doesn't exist, can't collect libraries:", conanfile.output)

        # Use cpp_info.libdirs
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = conanfile.collect_libs()
        self.assertEqual(["customlib", "mylib"], result)

        # Custom folder with multiple libdirs should only collect from custom folder
        self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
        result = conanfile.collect_libs(folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Unicity of lib names
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo("", "")
        custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(custom_mylib_path, "")
        save(lib_mylib_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)

        # Warn lib folder does not exist with correct result
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo("", "")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(lib_mylib_path, "")
        no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
        conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)
        self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                      % no_folder_path, conanfile.output)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Needs symlinks support")
    def test_self_collect_libs_symlinks(self):
        # Keep only the shortest lib name per group of symlinks
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo("", "")
        version_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.1.0.0.dylib")
        soversion_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.1.dylib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.dylib")
        lib_mylib2_path = os.path.join(conanfile.package_folder, "lib", "libmylib.2.dylib")
        lib_mylib3_path = os.path.join(conanfile.package_folder, "custom_folder", "libmylib.3.dylib")
        save(version_mylib_path, "")
        os.symlink(version_mylib_path, soversion_mylib_path)
        os.symlink(soversion_mylib_path, lib_mylib_path)
        save(lib_mylib2_path, "")
        save(lib_mylib3_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = conanfile.collect_libs()
        self.assertEqual(["mylib", "mylib.2", "mylib.3"], result)
