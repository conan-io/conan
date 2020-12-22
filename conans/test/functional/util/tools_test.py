# -*- coding: utf-8 -*-
import os
import platform
import unittest
import warnings

import pytest
import six

from conans.client import tools
from conans.client.conf import get_default_settings_yml
from conans.client.tools.files import which
from conans.client.tools.win import vswhere
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.env_reader import get_env


@unittest.skipUnless(platform.system() == "Windows", "Requires Visual Studio")
@pytest.mark.tool_visual_studio
class VisualStudioToolsTest(unittest.TestCase):
    output = TestBufferConanOutput()

    @unittest.skipIf(six.PY2, "Does not pass on Py2 with Pytest")
    def test_msvc_build_command(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"

        # test build_type and arch override, for multi-config packages
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cmd = tools.msvc_build_command(settings, "project.sln", build_type="Debug",
                                           arch="x86", output=self.output)
            self.assertEqual(len(w), 3)
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
            self.assertEqual(len(w), 3)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
        self.assertIn('msbuild "project.sln" /p:Configuration="Debug" '
                      '/p:UseEnv=false /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

    def test_vswhere_path(self):
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
