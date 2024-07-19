import os
import platform
import subprocess
import unittest

import pytest

from conan.tools.files import replace_in_file, collect_libs
from conans.model.build_info import CppInfo
from conans.model.layout import Infos
from conan.test.utils.mocks import ConanFileMock, RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output
from conan.test.utils.env import environment_update
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

        content = load(self.win_file, encoding="Windows-1252")
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

    def test_check_output_runner(self):
        original_temp = temp_folder()
        patched_temp = os.path.join(original_temp, "dir with spaces")
        payload = "hello world"
        output = check_output_runner("echo {}".format(payload), stderr=subprocess.STDOUT)
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

    @pytest.mark.skipif(platform.system() == "Windows", reason="Needs symlinks support")
    def test_collect_libs_symlinks(self):
        # Keep only the shortest lib name per group of symlinks
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo(set_defaults=True)
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
        result = collect_libs(conanfile)
        self.assertEqual(["mylib", "mylib.2", "mylib.3"], result)

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

    @pytest.mark.skipif(platform.system() == "Windows", reason="Needs symlinks support")
    def test_self_collect_libs_symlinks(self):
        # Keep only the shortest lib name per group of symlinks
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(temp_folder())
        conanfile.cpp_info = CppInfo(set_defaults=True)
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
        result = collect_libs(conanfile)
        self.assertEqual(["mylib", "mylib.2", "mylib.3"], result)
