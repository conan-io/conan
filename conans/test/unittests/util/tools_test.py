# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import sys
import unittest
import warnings
from collections import namedtuple

import mock
import requests
import six
from bottle import request, static_file
from mock.mock import mock_open, patch
from nose.plugins.attrib import attr
from parameterized import parameterized
from six import StringIO

from conans.client import tools
from conans.client.cache.cache import CONAN_CONF
from conans.client.conan_api import ConanAPIV1
from conans.client.conf import default_client_conf, default_settings_yml
from conans.client.output import ConanOutput
from conans.client.runner import ConanRunner
from conans.client.tools.files import replace_in_file, which
from conans.client.tools.oss import check_output, OSInfo
from conans.client.tools.win import vcvars_dict, vswhere
from conans.errors import ConanException, NotFoundException
from conans.model.build_info import CppInfo
from conans.model.settings import Settings
from conans.test.utils.conanfile import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import StoppableThreadBottle, TestBufferConanOutput, TestClient
from conans.tools import get_global_instances
from conans.util.env_reader import get_env
from conans.util.files import load, md5, mkdir, save


class RunnerMock(object):
    def __init__(self, return_ok=True):
        self.command_called = None
        self.return_ok = return_ok

    def __call__(self, command, output, win_bash=False, subsystem=None):  # @UnusedVariable
        self.command_called = command
        self.win_bash = win_bash
        self.subsystem = subsystem
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

    def replace_paths_test(self):
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

    def load_save_test(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        save(path, u"äüïöñç")
        content = load(path)
        self.assertEqual(content, u"äüïöñç")

    def md5_test(self):
        result = md5(u"äüïöñç")
        self.assertEqual("dfcc3d74aa447280a7ecfdb98da55174", result)

    def cpu_count_test(self):
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

    def get_env_unit_test(self):
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
        conf = default_client_conf.replace("\n[proxies]", "\n[proxies]\nhttp = http://myproxy.com")
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

    @unittest.skipUnless(platform.system() == "Windows", "Requires vswhere")
    def msvc_build_command_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"

        # test build_type and arch override, for multi-config packages
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cmd = tools.msvc_build_command(settings, "project.sln", build_type="Debug",
                                           arch="x86", output=self.output)
            self.assertEqual(len(w), 2)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
        self.assertIn('msbuild "project.sln" /p:Configuration="Debug" '
                      '/p:UseEnv=false /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

        # tests errors if args not defined
        with six.assertRaisesRegex(self, ConanException, "Cannot build_sln_command"):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                tools.msvc_build_command(settings, "project.sln", output=self.output)
                self.assertEqual(len(w), 2)
                self.assertTrue(issubclass(w[0].category, DeprecationWarning))
        settings.arch = "x86"
        with six.assertRaisesRegex(self, ConanException, "Cannot build_sln_command"):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                tools.msvc_build_command(settings, "project.sln", output=self.output)
                self.assertEqual(len(w), 2)
                self.assertTrue(issubclass(w[0].category, DeprecationWarning))

        # successful definition via settings
        settings.build_type = "Debug"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cmd = tools.msvc_build_command(settings, "project.sln", output=self.output)
            self.assertEqual(len(w), 2)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
        self.assertIn('msbuild "project.sln" /p:Configuration="Debug" '
                      '/p:UseEnv=false /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

    @unittest.skipUnless(platform.system() == "Windows", "Requires vswhere")
    def vswhere_description_strip_test(self):
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

    @unittest.skipUnless(platform.system() == "Windows", "Requires vswhere")
    def vswhere_path_test(self):
        """
        Locate vswhere in PATH or in ProgramFiles
        """
        # vswhere not found
        with tools.environment_append({"ProgramFiles": None, "ProgramFiles(x86)": None, "PATH": ""}):
            with six.assertRaisesRegex(self, ConanException, "Cannot locate vswhere"):
                vswhere()
        # vswhere in ProgramFiles but not in PATH
        program_files = get_env("ProgramFiles(x86)") or get_env("ProgramFiles")
        vswhere_path = None
        if program_files:
            expected_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                         "vswhere.exe")
            if os.path.isfile(expected_path):
                vswhere_path = expected_path
                with tools.environment_append({"PATH": ""}):
                    self.assertTrue(vswhere())
        # vswhere in PATH but not in ProgramFiles
        env = {"ProgramFiles": None, "ProgramFiles(x86)": None}
        if not which("vswhere") and vswhere_path:
                vswhere_folder = os.path.join(program_files, "Microsoft Visual Studio", "Installer")
                env.update({"PATH": [vswhere_folder]})
        with tools.environment_append(env):
            self.assertTrue(vswhere())

    def vcvars_echo_test(self):
        if platform.system() != "Windows":
            return
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        cmd = tools.vcvars_command(settings, output=self.output)
        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=True, output=output)
        runner(cmd + " && set vs140comntools")
        self.assertIn("vcvarsall.bat", str(output))
        self.assertIn("VS140COMNTOOLS=", str(output))
        with tools.environment_append({"VisualStudioVersion": "14"}):
            output = TestBufferConanOutput()
            runner = ConanRunner(print_commands_to_output=True, output=output)
            cmd = tools.vcvars_command(settings, output=self.output)
            runner(cmd + " && set vs140comntools")
            self.assertNotIn("vcvarsall.bat", str(output))
            self.assertIn("Conan:vcvars already set", str(output))
            self.assertIn("VS140COMNTOOLS=", str(output))

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_env_not_duplicated_path_test(self):
        """vcvars is not looking at the current values of the env vars, with PATH it is a problem because you
        can already have set some of the vars and accumulate unnecessary entries."""
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.arch_build = "x86_64"

        # Set the env with a PATH containing the vcvars paths
        tmp = tools.vcvars_dict(settings, only_diff=False, output=self.output)
        tmp = {key.lower(): value for key, value in tmp.items()}
        with tools.environment_append({"path": tmp["path"]}):
            previous_path = os.environ["PATH"].split(";")
            # Duplicate the path, inside the tools.vcvars shouldn't have repeated entries in PATH
            with tools.vcvars(settings, output=self.output):
                path = os.environ["PATH"].split(";")
                values_count = {value: path.count(value) for value in path}
                for value, counter in values_count.items():
                    if value and counter > 1 and previous_path.count(value) != counter:
                        # If the entry was already repeated before calling "tools.vcvars" we keep it
                        self.fail("The key '%s' has been repeated" % value)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_filter_known_paths_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.arch_build = "x86_64"
        with tools.environment_append({"PATH": ["custom_path", "WindowsFake"]}):
            tmp = tools.vcvars_dict(settings, only_diff=False,
                                    filter_known_paths=True, output=self.output)
            with tools.environment_append(tmp):
                self.assertNotIn("custom_path", os.environ["PATH"])
                self.assertIn("WindowsFake",  os.environ["PATH"])
            tmp = tools.vcvars_dict(settings, only_diff=False,
                                    filter_known_paths=False, output=self.output)
            with tools.environment_append(tmp):
                self.assertIn("custom_path", os.environ["PATH"])
                self.assertIn("WindowsFake", os.environ["PATH"])

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_amd64_32_cross_building_support_test(self):
        # amd64_x86 crossbuilder
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.arch_build = "x86_64"
        cmd = tools.vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat" amd64_x86', cmd)

        # It follows arch_build first
        settings.arch_build = "x86"
        cmd = tools.vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat" x86', cmd)

    def vcvars_raises_when_not_found_test(self):
        text = """
os: [Windows]
compiler:
    Visual Studio:
        version: ["5"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "5"
        with six.assertRaisesRegex(self, ConanException,
                                   "VS non-existing installation: Visual Studio 5"):
            output = ConanOutput(StringIO())
            tools.vcvars_command(settings, output=output)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_constrained_test(self):
        new_out = StringIO()
        output = ConanOutput(new_out)

        text = """os: [Windows]
compiler:
    Visual Studio:
        version: ["14"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        with six.assertRaisesRegex(self, ConanException,
                                   "compiler.version setting required for vcvars not defined"):
            tools.vcvars_command(settings, output=output)

        new_out = StringIO()
        output = ConanOutput(new_out)
        settings.compiler.version = "14"
        with tools.environment_append({"vs140comntools": "path/to/fake"}):
            tools.vcvars_command(settings, output=output)
            with tools.environment_append({"VisualStudioVersion": "12"}):
                with six.assertRaisesRegex(self, ConanException,
                                           "Error, Visual environment already set to 12"):
                    tools.vcvars_command(settings, output=output)

            with tools.environment_append({"VisualStudioVersion": "12"}):
                # Not raising
                tools.vcvars_command(settings, force=True, output=output)

    def vcvars_context_manager_test(self):
        conanfile = """
from conans import ConanFile, tools

class MyConan(ConanFile):
    name = "MyConan"
    version = "0.1"
    settings = "os", "compiler"

    def build(self):
        with tools.vcvars(self.settings, only_diff=True):
            self.output.info("VCINSTALLDIR set to: " + str(tools.get_env("VCINSTALLDIR")))
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})

        if platform.system() == "Windows":
            client.run("create . conan/testing")
            self.assertNotIn("VCINSTALLDIR set to: None", client.out)
        else:
            client.run("create . conan/testing")
            self.assertIn("VCINSTALLDIR set to: None", client.out)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_dict_diff_test(self):
        text = """
os: [Windows]
compiler:
    Visual Studio:
        version: ["14"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        with tools.environment_append({"MYVAR": "1"}):
            ret = vcvars_dict(settings, only_diff=False, output=self.output)
            self.assertIn("MYVAR", ret)
            self.assertIn("VCINSTALLDIR", ret)

            ret = vcvars_dict(settings, output=self.output)
            self.assertNotIn("MYVAR", ret)
            self.assertIn("VCINSTALLDIR", ret)

        my_lib_paths = "C:\\PATH\TO\MYLIBS;C:\\OTHER_LIBPATH"
        with tools.environment_append({"LIBPATH": my_lib_paths}):
            ret = vcvars_dict(settings, only_diff=False, output=self.output)
            str_var_value = os.pathsep.join(ret["LIBPATH"])
            self.assertTrue(str_var_value.endswith(my_lib_paths))

            # Now only a diff, it should return the values as a list, but without the old values
            ret = vcvars_dict(settings, only_diff=True, output=self.output)
            self.assertEqual(ret["LIBPATH"], str_var_value.split(os.pathsep)[0:-2])

            # But if we apply both environments, they are composed correctly
            with tools.environment_append(ret):
                self.assertEqual(os.environ["LIBPATH"], str_var_value)

    def vcvars_dict_test(self):
        # https://github.com/conan-io/conan/issues/2904
        output_with_newline_and_spaces = """
     PROCESSOR_ARCHITECTURE=AMD64

PROCESSOR_IDENTIFIER=Intel64 Family 6 Model 158 Stepping 9, GenuineIntel


 PROCESSOR_LEVEL=6

PROCESSOR_REVISION=9e09


set nl=^
env_var=
without_equals_sign

ProgramFiles(x86)=C:\Program Files (x86)

"""

        def vcvars_command_mock(settings, arch, compiler_version, force, vcvars_ver, winsdk_version,
                                output):  # @UnusedVariable
            return "unused command"

        def subprocess_check_output_mock(cmd):
            self.assertIn("unused command", cmd)
            return output_with_newline_and_spaces

        with mock.patch('conans.client.tools.win.vcvars_command', new=vcvars_command_mock):
            with patch('conans.client.tools.win.check_output', new=subprocess_check_output_mock):
                vcvars = tools.vcvars_dict(None, only_diff=False, output=self.output)
                self.assertEqual(vcvars["PROCESSOR_ARCHITECTURE"], "AMD64")
                self.assertEqual(vcvars["PROCESSOR_IDENTIFIER"],
                                 "Intel64 Family 6 Model 158 Stepping 9, GenuineIntel")
                self.assertEqual(vcvars["PROCESSOR_LEVEL"], "6")
                self.assertEqual(vcvars["PROCESSOR_REVISION"], "9e09")
                self.assertEqual(vcvars["ProgramFiles(x86)"], "C:\Program Files (x86)")

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def run_in_bash_test(self):

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
            self.assertIn('^&^& PATH=\\^"/cygdrive/other/path:/cygdrive/path/to/somewhere:$PATH\\^" '
                          '^&^& MYVAR=34 ^&^& a_command.bat ^', conanfile._conan_runner.command)

    @attr("slow")
    def download_retries_test(self):
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

        # Connection error
        # Default behaviour
        with six.assertRaisesRegex(self, ConanException, "Error downloading"):
            tools.download("http://fakeurl3.es/nonexists",
                           os.path.join(temp_folder(), "file.txt"), out=out,
                           requester=requests)
        self.assertEqual(str(out).count("Waiting 5 seconds to retry..."), 1)

        # Retry arguments override defaults
        with six.assertRaisesRegex(self, ConanException, "Error downloading"):
            tools.download("http://fakeurl3.es/nonexists",
                           os.path.join(temp_folder(), "file.txt"), out=out,
                           requester=requests,
                           retry=2, retry_wait=1)
        self.assertEqual(str(out).count("Waiting 1 seconds to retry..."), 2)

        # Retry default values from the config
        class MockRequester(object):
            retry = 2
            retry_wait = 0

            def get(self, *args, **kwargs):
                return requests.get(*args, **kwargs)

        with six.assertRaisesRegex(self, ConanException, "Error downloading"):
            tools.download("http://fakeurl3.es/nonexists",
                           os.path.join(temp_folder(), "file.txt"), out=out,
                           requester=MockRequester())
        self.assertEqual(str(out).count("Waiting 0 seconds to retry..."), 2)

        # Not found error
        with six.assertRaisesRegex(self, NotFoundException, "Not found: "):
            tools.download("http://google.es/FILE_NOT_FOUND",
                           os.path.join(temp_folder(), "README.txt"), out=out,
                           requester=requests,
                           retry=2, retry_wait=0)

        # And OK
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
                           overwrite=True, requester=requests, out=out)

        # Authorized
        tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                       auth=("user", "passwd"), overwrite=True, requester=requests, out=out)

        # Authorized using headers
        tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                       headers={"Authorization": "Basic dXNlcjpwYXNzd2Q="}, overwrite=True,
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
        ["iOS", "armv7", None, "arm-apple-darwin"],
        ["watchOS", "armv7k", None, "arm-apple-darwin"],
        ["watchOS", "armv8_32", None, "aarch64-apple-darwin"],
        ["tvOS", "armv8", None, "aarch64-apple-darwin"],
        ["tvOS", "armv8.3", None, "aarch64-apple-darwin"],
        ["Emscripten", "asm.js", None, "asmjs-local-emscripten"],
        ["Emscripten", "wasm", None, "wasm32-local-emscripten"],
        ["AIX", "ppc32", None, "rs6000-ibm-aix"],
        ["AIX", "ppc64", None, "powerpc-ibm-aix"],
        ["Neutrino", "armv7", None, "arm-nto-qnx"],
        ["Neutrino", "armv8", None, "aarch64-nto-qnx"],
        ["Neutrino", "sh4le", None, "sh4-nto-qnx"],
        ["Neutrino", "ppc32be", None, "powerpcbe-nto-qnx"]
    ])
    def get_gnu_triplet_test(self, os, arch, compiler, expected_triplet):
        triplet = tools.get_gnu_triplet(os, arch, compiler)
        self.assertEqual(triplet, expected_triplet,
                         "triplet did not match for ('%s', '%s', '%s')" % (os, arch, compiler))

    def get_gnu_triplet_on_windows_without_compiler_test(self):
        with self.assertRaises(ConanException):
            tools.get_gnu_triplet("Windows", "x86")

    def detect_windows_subsystem_test(self):
        # Dont raise test
        result = OSInfo.detect_windows_subsystem()
        if not OSInfo.bash_path() or platform.system() != "Windows":
            self.assertEqual(None, result)
        else:
            self.assertEqual(str, type(result))

    @attr('slow')
    @attr('local_bottle')
    def get_filename_download_test(self):
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
        with six.assertRaisesRegex(self, ConanException,
                                   "Cannot deduce file name form url. Use 'filename' parameter."):
            tools.get("http://localhost:%s/?file=1" % thread.port, output=out)

        # Test: Works with filename parameter instead of '?file=1'
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/?file=1" % thread.port, filename="sample.tar.gz",
                      requester=requests, output=out)
            self.assertTrue(os.path.exists("test_folder"))

        # Test: Use a different endpoint but still not the filename one
        with tools.chdir(tools.mkdir_tmp()):
            from zipfile import BadZipfile
            with self.assertRaises(BadZipfile):
                tools.get("http://localhost:%s/this_is_not_the_file_name" % thread.port,
                          requester=requests, output=out)
            tools.get("http://localhost:%s/this_is_not_the_file_name" % thread.port,
                      filename="sample.tar.gz", requester=requests, output=out)
            self.assertTrue(os.path.exists("test_folder"))
        thread.stop()

        with six.assertRaisesRegex(self, ConanException, "Error"):
            tools.get("http://localhost:%s/error_url" % thread.port,
                      filename="fake_sample.tar.gz", requester=requests, output=out, verify=False,
                      retry=2, retry_wait=0)

        # Not found error
        self.assertEqual(str(out).count("Waiting 0 seconds to retry..."), 2)

    @attr('slow')
    @attr('local_bottle')
    def get_gunzip_test(self):
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
                      output=out)
            self.assertTrue(os.path.exists("test.txt"))
            self.assertEqual(load("test.txt"), "hello world zipped!")
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/test.txt.gz" % thread.port, requester=requests,
                      output=out, destination="myfile.doc")
            self.assertTrue(os.path.exists("myfile.doc"))
            self.assertEqual(load("myfile.doc"), "hello world zipped!")
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/test.txt.gz" % thread.port, requester=requests,
                      output=out, destination="mytemp/myfile.txt")
            self.assertTrue(os.path.exists("mytemp/myfile.txt"))
            self.assertEqual(load("mytemp/myfile.txt"), "hello world zipped!")

        thread.stop()

    def unix_to_dos_unit_test(self):

        def save_file(contents):
            tmp = temp_folder()
            filepath = os.path.join(tmp, "a_file.txt")
            save(filepath, contents)
            return filepath

        fp = save_file(b"a line\notherline\n")
        if platform.system() != "Windows":
            output = check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertNotIn("CRLF", str(output))

            tools.unix2dos(fp)
            output = check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertIn("CRLF", str(output))
        else:
            fc = tools.load(fp)
            self.assertNotIn("\r\n", fc)
            tools.unix2dos(fp)
            fc = tools.load(fp)
            self.assertIn("\r\n", fc)

        self.assertEqual("a line\r\notherline\r\n", str(tools.load(fp)))

        fp = save_file(b"a line\r\notherline\r\n")
        if platform.system() != "Windows":
            output = check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertIn("CRLF", str(output))

            tools.dos2unix(fp)
            output = check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertNotIn("CRLF", str(output))
        else:
            fc = tools.load(fp)
            self.assertIn("\r\n", fc)
            tools.dos2unix(fp)
            fc = tools.load(fp)
            self.assertNotIn("\r\n", fc)

        self.assertEqual("a line\notherline\n", str(tools.load(fp)))

    def unix_to_dos_conanfile_test(self):
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

    def collect_libs_test(self):
        conanfile = ConanFileMock()
        # Without package_folder
        conanfile.package_folder = None
        result = tools.collect_libs(conanfile)
        self.assertEqual([], result)

        # Default behavior
        conanfile.package_folder = temp_folder()
        mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(mylib_path, "")
        conanfile.cpp_info = CppInfo("")
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

        # Warn same lib different folders
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(custom_mylib_path, "")
        save(lib_mylib_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)
        self.assertIn("Library 'mylib' was either already found in a previous "
                      "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                      "different file extension", conanfile.output)

        # Warn lib folder does not exist with correct result
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(lib_mylib_path, "")
        no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
        conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)
        self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                      % no_folder_path, conanfile.output)

    def self_collect_libs_test(self):
        conanfile = ConanFileMock()
        # Without package_folder
        conanfile.package_folder = None
        result = conanfile.collect_libs()
        self.assertEqual([], result)
        self.assertIn("'self.collect_libs' is deprecated, use 'tools.collect_libs(self)' instead",
                      conanfile.output)

        # Default behavior
        conanfile.package_folder = temp_folder()
        mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(mylib_path, "")
        conanfile.cpp_info = CppInfo("")
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

        # Warn same lib different folders
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(custom_mylib_path, "")
        save(lib_mylib_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)
        self.assertIn("Library 'mylib' was either already found in a previous "
                      "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                      "different file extension", conanfile.output)

        # Warn lib folder does not exist with correct result
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(lib_mylib_path, "")
        no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
        conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)
        self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                      % no_folder_path, conanfile.output)
