import os
import platform
from shutil import which

import pytest

from conan.internal.api.detect.detect_vs import vswhere
from conan.errors import ConanException
from conan.test.utils.env import environment_update


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Visual Studio")
@pytest.mark.tool("visual_studio")
class TestVisualStudioTools:

    def test_vswhere_not_found(self):
        """
        Locate vswhere in PATH or in ProgramFiles
        """
        # vswhere not found
        with environment_update({"ProgramFiles": None, "ProgramFiles(x86)": None, "PATH": ""}):
            with pytest.raises(ConanException) as e:
                vswhere()
            assert "Cannot locate vswhere" in str(e.value)

    def test_vswhere_path(self):
        # vswhere in ProgramFiles but not in PATH
        program_files = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
        vswhere_path = None
        if program_files:
            expected_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                         "vswhere.exe")
            if os.path.isfile(expected_path):
                vswhere_path = expected_path
                with environment_update({"PATH": ""}):
                    assert vswhere()

        # vswhere in PATH but not in ProgramFiles
        env = {"ProgramFiles": None, "ProgramFiles(x86)": None}
        if not which("vswhere") and vswhere_path:
            env.update({"PATH": os.path.dirname(vswhere_path)})
        with environment_update(env):
            assert vswhere()
