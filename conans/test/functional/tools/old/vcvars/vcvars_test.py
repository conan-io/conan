import os
import platform
import unittest

import mock
import pytest
import six
from mock.mock import patch
from six import StringIO

from conans import Settings
from conans.client import tools
from conans.client.conf import get_default_settings_yml
from conans.client.output import ConanOutput
from conans.client.runner import ConanRunner
from conans.client.tools.win import vcvars_dict
from conans.errors import ConanException
from conans.test.utils.tools import TestClient
from conans.test.utils.mocks import TestBufferConanOutput


class VCVarsTest(unittest.TestCase):
    def setUp(self):
        self.output = TestBufferConanOutput()

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_echo(self):
        settings = Settings.loads(get_default_settings_yml())
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

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_with_store_echo(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "WindowsStore"
        settings.os.version = "8.1"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        cmd = tools.vcvars_command(settings, output=self.output)
        self.assertIn("store 8.1", cmd)
        with tools.environment_append({"VisualStudioVersion": "14"}):
            cmd = tools.vcvars_command(settings, output=self.output)
            self.assertEqual("echo Conan:vcvars already set", cmd)

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_env_not_duplicated_path(self):
        """vcvars is not looking at the current values of the env vars, with PATH it is a problem
        because you can already have set some of the vars and accumulate unnecessary entries."""
        settings = Settings.loads(get_default_settings_yml())
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
                    if value and (counter > 1) and previous_path.count(value) != counter:
                        # If the entry was already repeated before calling "tools.vcvars" we keep it
                        self.fail("The key '%s' has been repeated" % value)

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_filter_known_paths(self):
        settings = Settings.loads(get_default_settings_yml())
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

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_amd64_32_cross_building_support(self):
        # amd64_x86 crossbuilder
        settings = Settings.loads(get_default_settings_yml())
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

    def test_vcvars_raises_when_not_found(self):
        text = """
os: [Windows]
arch: [x86_64]
arch_build: [x86_64]
compiler:
    Visual Studio:
        version: ["5"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "5"
        settings.arch = "x86_64"
        settings.arch_build = "x86_64"
        with six.assertRaisesRegex(self, ConanException,
                                   "VS non-existing installation: Visual Studio 5"):
            output = ConanOutput(StringIO())
            tools.vcvars_command(settings, output=output)

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_constrained(self):
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

    def test_vcvars_context_manager(self):
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

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_vcvars_dict_diff(self):
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

        my_lib_paths = "C:\\PATH\\TO\\MYLIBS;C:\\OTHER_LIBPATH"
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

    def test_vcvars_dict(self):
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

        def vcvars_command_mock(*args, **kwargs):
            return "unused command"

        def subprocess_check_output_mock(cmd):
            self.assertIn("unused command", cmd)
            return output_with_newline_and_spaces

        with mock.patch('conans.client.tools.win.vcvars_command', new=vcvars_command_mock):
            with patch('conans.client.tools.win.check_output_runner',
                       new=subprocess_check_output_mock):
                vcvars = tools.vcvars_dict(None, only_diff=False, output=self.output)
                self.assertEqual(vcvars["PROCESSOR_ARCHITECTURE"], "AMD64")
                self.assertEqual(vcvars["PROCESSOR_IDENTIFIER"],
                                 "Intel64 Family 6 Model 158 Stepping 9, GenuineIntel")
                self.assertEqual(vcvars["PROCESSOR_LEVEL"], "6")
                self.assertEqual(vcvars["PROCESSOR_REVISION"], "9e09")
                self.assertEqual(vcvars["ProgramFiles(x86)"], "C:\\Program Files (x86)")
