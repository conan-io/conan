# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import unittest

import pytest
from mock.mock import mock_open, patch

from conan.tools.files import replace_in_file, collect_libs
from conans.client import tools
from conans.client.conf.detect_vs import vswhere
from conans.model.layout import Infos
from conans.test.utils.mocks import ConanFileMock, RedirectedTestOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import redirect_output
from conans.util.env import get_env, environment_update
from conans.util.files import load, md5, save
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

    def __call__(self, command):  # @UnusedVariable
        self.command_called = command
        return 0 if self.return_ok else 1


class ReplaceInFileTest(unittest.TestCase):
    def setUp(self):
        text = u'J\xe2nis\xa7'
        self.tmp_folder = temp_folder()

        self.win_file = os.path.join(self.tmp_folder, "win_encoding.txt")
        text = text.encode("Windows-1252", "ignore")
        with open(self.win_file, "wb") as handler:
            handler.write(text)

    def test_replace_in_file(self):
        replace_in_file(ConanFileMock(), self.win_file, "nis", "nus", encoding="Windows-1252")

        content = load(self.win_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)


class ToolsTest(unittest.TestCase):

    def test_load_save(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        save(path, u"äüïöñç")
        content = load(path)
        self.assertEqual(content, u"äüïöñç")

    def test_md5(self):
        result = md5(u"äüïöñç")
        self.assertEqual("dfcc3d74aa447280a7ecfdb98da55174", result)

    def test_get_env_unit(self):
        """
        Unit tests get_env
        """
        # Test default
        self.assertIsNone(
            get_env("NOT_DEFINED", environment={}),
            None
        )
        # Test defined default
        self.assertEqual(
            get_env("NOT_DEFINED_KEY", default="random_default", environment={}),
            "random_default"
        )
        # Test return defined string
        self.assertEqual(
            get_env("FROM_STR", default="", environment={"FROM_STR": "test_string_value"}),
            "test_string_value"
        )
        # Test boolean conversion
        self.assertEqual(
            get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "1"}),
            True
        )
        self.assertEqual(
            get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": "0"}),
            False
        )
        self.assertEqual(
            get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "True"}),
            True
        )
        self.assertEqual(
            get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": ""}),
            False
        )
        # Test int conversion
        self.assertEqual(
            get_env("TO_INT", default=2, environment={"TO_INT": "1"}),
            1
        )
        # Test float conversion
        self.assertEqual(
            get_env("TO_FLOAT", default=2.0, environment={"TO_FLOAT": "1"}),
            1.0
        ),
        # Test list conversion
        self.assertEqual(
            get_env("TO_LIST", default=[], environment={"TO_LIST": "1,2,3"}),
            ["1", "2", "3"]
        )
        self.assertEqual(
            get_env("TO_LIST_NOT_TRIMMED", default=[], environment={"TO_LIST_NOT_TRIMMED":
                                                                          " 1 , 2 , 3 "}),
            ["1", "2", "3"]
        )

    def test_environment_nested(self):
        with environment_update({"A": "1", "Z": "40"}):
            with environment_update({"A": "1", "B": "2"}):
                with environment_update({"A": "2", "B": "2"}):
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
        myoutput = myoutput.encode()
        myrunner = mock_open()
        myrunner.check_output = lambda x: myoutput
        with patch('conans.client.conf.detect_vs.subprocess', myrunner):
            json = vswhere()
            self.assertNotIn("descripton", json)

    def test_check_output_runner(self):
        original_temp = temp_folder()
        patched_temp = os.path.join(original_temp, "dir with spaces")
        payload = "hello world"
        output = check_output_runner(["echo", payload], stderr=subprocess.STDOUT)
        self.assertIn(payload, str(output))


class CollectLibTestCase(unittest.TestCase):

    def test_collect_libs(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            conanfile = ConanFileMock()
            # Without package_folder
            result = collect_libs(conanfile)
            self.assertEqual([], result)

            # Default behavior
            conanfile.folders.set_base_package(temp_folder())
            mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(mylib_path, "")
            conanfile.cpp = Infos()
            result = collect_libs(conanfile)
            self.assertEqual(["mylib"], result)

            # Custom folder
            customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
            save(customlib_path, "")
            result = collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Custom folder doesn't exist
            result = collect_libs(conanfile, folder="fake_folder")
            self.assertEqual([], result)
            self.assertIn("Lib folder doesn't exist, can't collect libraries:", output.getvalue())
            output.clear()

            # Use cpp_info.libdirs
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
            result = collect_libs(conanfile)
            self.assertEqual(["customlib", "mylib"], result)

            # Custom folder with multiple libdirs should only collect from custom folder
            self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
            result = collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Warn same lib different folders
            conanfile = ConanFileMock()
            conanfile.folders.set_base_package(temp_folder())
            conanfile.cpp = Infos()
            custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(custom_mylib_path, "")
            save(lib_mylib_path, "")
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]

            output.clear()
            result = collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("Library 'mylib' was either already found in a previous "
                          "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                          "different file extension", output.getvalue())

            # Warn lib folder does not exist with correct result
            conanfile = ConanFileMock()
            conanfile.folders.set_base_package(temp_folder())
            conanfile.cpp = Infos()
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(lib_mylib_path, "")
            no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
            conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
            output.clear()
            result = collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                          % no_folder_path, output.getvalue())

    def test_self_collect_libs(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            conanfile = ConanFileMock()
            # Without package_folder
            result = collect_libs(conanfile)
            self.assertEqual([], result)

            # Default behavior
            conanfile.folders.set_base_package(temp_folder())
            mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(mylib_path, "")
            conanfile.cpp = Infos()
            result = collect_libs(conanfile)
            self.assertEqual(["mylib"], result)

            # Custom folder
            customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
            save(customlib_path, "")
            result = collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Custom folder doesn't exist
            output.clear()
            result = collect_libs(conanfile, folder="fake_folder")
            self.assertEqual([], result)
            self.assertIn("Lib folder doesn't exist, can't collect libraries:", output.getvalue())

            # Use cpp_info.libdirs
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
            result = collect_libs(conanfile)
            self.assertEqual(["customlib", "mylib"], result)

            # Custom folder with multiple libdirs should only collect from custom folder
            self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
            result = collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Warn same lib different folders
            conanfile = ConanFileMock()
            conanfile.folders.set_base_package(temp_folder())
            conanfile.cpp = Infos()
            custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(custom_mylib_path, "")
            save(lib_mylib_path, "")
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
            output.clear()
            result = collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("Library 'mylib' was either already found in a previous "
                          "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                          "different file extension", output.getvalue())

            # Warn lib folder does not exist with correct result
            conanfile = ConanFileMock()
            conanfile.folders.set_base_package(temp_folder())
            conanfile.cpp = Infos()
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(lib_mylib_path, "")
            no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
            conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
            output.clear()
            result = collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                          % no_folder_path, output.getvalue())
