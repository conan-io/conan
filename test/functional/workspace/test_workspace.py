import os
import platform
import shutil

import pytest

from conan.api.subapi.workspace import WorkspaceAPI
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import TestClient
from conan.tools.files import replace_in_file

WorkspaceAPI.TEST_ENABLED = "will_break_next"


@pytest.mark.tool("cmake")
def test_build():
    # This is not using the meta-project at all
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace build")
    assert "conanfile.py (app1/0.1): Calling build()" in c.out
    assert "conanfile.py (app1/0.1): Running CMake.build()" in c.out
    # it works without failing


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_metabuild():
    # This is using the meta-project
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace super-install")
    assert os.path.exists(os.path.join(c.current_folder, "CMakeUserPresets.json"))
    build_folder = "build/Release" if platform.system() != "Windows" else "build"
    assert os.path.exists(os.path.join(c.current_folder, build_folder, "generators"))
    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")
    assert "Conan: Target declared 'mymath::mymath'" in c.out
    assert "Adding project: liba" in c.out
    assert "Adding project: libb" in c.out
    assert "Adding project: app1" in c.out
    c.run_command("cmake --build --preset conan-release")
    # it doesn't fail


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_new_template_and_different_folder():
    """
    Issue related: https://github.com/conan-io/conan/issues/18813
    """
    c = TestClient()
    c.run("new workspace")
    shutil.move(os.path.join(c.current_folder, "liba"), os.path.join(c.current_folder, "libX"))
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "conanws.yml"),
                    "  - path: liba",
                    "  - path: libX")
    c.run("workspace super-install")
    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")  # it does not fail
    assert "Adding project: liba" in c.out
    assert "Adding project: libb" in c.out
    assert "Adding project: app1" in c.out
