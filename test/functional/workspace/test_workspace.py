import os
import platform
import textwrap

import pytest

from conan.api.subapi.workspace import WorkspaceAPI
from conan.internal.util.files import chdir
from conan.test.utils.tools import TestClient

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
    assert "Calling build() for the product app1/0.1" in c.out
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
    c.run("workspace install")
    assert os.path.exists(os.path.join(c.current_folder, "CMakeUserPresets.json"))
    build_folder = "build/Release" if platform.system() != "Windows" else "build"
    assert os.path.exists(os.path.join(c.current_folder, build_folder, "generators"))
    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")
    assert "Conan: Target declared 'mymath::mymath'" in c.out
    assert "Adding project liba" in c.out
    assert "Adding project libb" in c.out
    assert "Adding project app1" in c.out
    c.run_command("cmake --build --preset conan-release")
    # it doesn't fail


# @pytest.mark.tool("cmake", "3.27")
def test_relative_paths():
    # This is using the meta-project
    c = TestClient()
    c.run("new cmake_lib -d name=liba --output=liba")
    c.run("new cmake_exe -d name=app1 -d requires=liba/0.1 --output=app1")
    c.run("new cmake_lib -d name=libb --output=other/libb")
    c.run("new cmake_exe -d name=app2 -d requires=libb/0.1 --output=other/app2")
    c.run("workspace init mywks")
    c.run("workspace init otherwks")
    # cd mywks
    with c.chdir("mywks"):
        c.run("workspace add ../liba")
        c.run("workspace add ../app1 --product")
        c.run("workspace build")
        conanws_yml = textwrap.dedent("""\
        editables:
          app1/0.1:
            path: ../app1
          liba/0.1:
            path: ../liba
        products:
        - ../app1
        """)
        assert conanws_yml == c.load("conanws.yml")
    # cd otherwks
    with c.chdir("otherwks"):
        c.run("workspace add ../other/libb")
        c.run("workspace add ../other/app2 --product")
        c.run("workspace build")
        conanws_yml = textwrap.dedent("""\
        editables:
          app2/0.1:
            path: ../other/app2
          libb/0.1:
            path: ../other/libb
        products:
        - ../other/app2
        """)
        assert conanws_yml == c.load("conanws.yml")

    ext = ".exe" if platform.system() == "Windows" else ""
    assert os.path.exists(os.path.join(c.current_folder, "app1", "build", "Release", f"app1{ext}"))
    assert os.path.exists(os.path.join(c.current_folder, "other", "app2", "build", "Release", f"app2{ext}"))
