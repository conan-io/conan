import platform

import pytest

from conan.internal.workspace import Workspace
from conan.test.utils.tools import TestClient


Workspace.TEST_ENABLED = "will_break_next"


@pytest.mark.tool("cmake")
def test():
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace build")
    # it works without failing


@pytest.mark.tool("cmake", "3.25")
def test_build():
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace install")
    print(c.out)
    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")
    print(c.out)
    c.run_command("cmake --build --preset conan-release")
    print(c.out)
