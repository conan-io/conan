import platform
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


# TODO: add versions for all platforms
@pytest.mark.skipif(platform.system() != "Windows", reason="Only versions for Windows at the moment")
class TestToolsCustomVersions:

    @pytest.mark.tool_cmake(version="3.16")
    def test_custom_cmake_3_16(self):
        client = TestClient()
        client.run_command('cmake --version')
        assert "cmake version 3.16" in client.out

    @pytest.mark.tool_cmake(version="3.17")
    def test_custom_cmake_3_17(self):
        client = TestClient()
        client.run_command('cmake --version')
        assert "cmake version 3.17" in client.out

    @pytest.mark.tool_mingw64
    @pytest.mark.tool_cmake(version="3.16")
    def test_custom_cmake_mingw64(self):
        client = TestClient()
        client.run_command('cmake --version')
        assert "cmake version 3.16" in client.out
        main = gen_function_cpp(name="main")
        cmakelist = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(App C CXX)
            add_executable(app app.cpp)
            """)
        client.save({"CMakeLists.txt": cmakelist, "app.cpp": main})
        client.run_command('cmake . -G "MinGW Makefiles"')
        client.run_command("cmake --build .")
