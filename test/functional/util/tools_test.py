import os
import platform
import unittest
from shutil import which

import pytest

from conans.client.conf.detect_vs import vswhere
from conans.errors import ConanException
from conan.test.utils.env import environment_update


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Visual Studio")
@pytest.mark.tool("visual_studio")
class VisualStudioToolsTest(unittest.TestCase):

    def test_vswhere_path(self):
        """
        Locate vswhere in PATH or in ProgramFiles
        """
        # vswhere not found
        with environment_update({"ProgramFiles": None, "ProgramFiles(x86)": None, "PATH": ""}):
            with self.assertRaisesRegex(ConanException, "Cannot locate vswhere"):
                vswhere()
        # vswhere in ProgramFiles but not in PATH
        program_files = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
        vswhere_path = None
        if program_files:
            expected_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                         "vswhere.exe")
            if os.path.isfile(expected_path):
                vswhere_path = expected_path
                with environment_update({"PATH": ""}):
                    self.assertTrue(vswhere())
        # vswhere in PATH but not in ProgramFiles
        env = {"ProgramFiles": None, "ProgramFiles(x86)": None}
        if not which("vswhere") and vswhere_path:
            vswhere_folder = os.path.join(program_files, "Microsoft Visual Studio", "Installer")
            env.update({"PATH": vswhere_folder})
        with environment_update(env):
            self.assertTrue(vswhere())
