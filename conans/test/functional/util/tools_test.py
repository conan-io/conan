# -*- coding: utf-8 -*-

import os
import platform
import subprocess
import unittest

import pytest

from conans.client import tools
from conans.client.tools.files import which
from conans.client.tools.win import vswhere
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.util.env_reader import get_env
from conans.util.files import save
from conans.util.runners import check_output_runner


class FunctionalToolsTest(unittest.TestCase):

    @pytest.mark.tool_file  # Needs the "file" command, not by default in linux
    @pytest.mark.skipif(which("file") is None,
                        reason="Needs the 'file' command, not by default in linux")
    def test_unix_to_dos_unit(self):
        def save_file(contents):
            tmp = temp_folder()
            filepath = os.path.join(tmp, "a_file.txt")
            save(filepath, contents)
            return filepath

        fp = save_file(b"a line\notherline\n")
        if platform.system() != "Windows":
            output = check_output_runner(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertNotIn("CRLF", str(output))

            tools.unix2dos(fp)
            output = check_output_runner(["file", fp], stderr=subprocess.STDOUT)
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
            output = check_output_runner(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertIn("CRLF", str(output))

            tools.dos2unix(fp)
            output = check_output_runner(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertNotIn("CRLF", str(output))
        else:
            fc = tools.load(fp)
            self.assertIn("\r\n", fc)
            tools.dos2unix(fp)
            fc = tools.load(fp)
            self.assertNotIn("\r\n", fc)

        self.assertEqual("a line\notherline\n", str(tools.load(fp)))


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Visual Studio")
@pytest.mark.tool_visual_studio
class VisualStudioToolsTest(unittest.TestCase):

    def test_vswhere_path(self):
        """
        Locate vswhere in PATH or in ProgramFiles
        """
        # vswhere not found
        with tools.environment_append({"ProgramFiles": None, "ProgramFiles(x86)": None, "PATH": ""}):
            with self.assertRaisesRegex(ConanException, "Cannot locate vswhere"):
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
