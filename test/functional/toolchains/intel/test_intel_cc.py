import pytest
import platform
import textwrap
import os

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
@pytest.mark.tool("intel_oneapi")
@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
class TestIntelCC:
    """Tests for Intel oneAPI C++/DPC++ compilers"""

    def test_intel_oneapi_and_dpcpp(self):
        client = TestClient()
        client.run("new cmake_exe -d name=hello -d version=0.1")
        intel_profile = textwrap.dedent("""
            [settings]
            os=Linux
            arch=x86_64
            compiler=intel-cc
            compiler.mode=dpcpp
            compiler.version=2026.0
            compiler.libcxx=libstdc++
            build_type=Release

            [conf]
            tools.intel:installation_path=/opt/intel/oneapi
            tools.build:compiler_executables={"c": "icx", "cpp": "icpx"}
            tools.build:cxxflags=["-fsycl"]
            tools.build:sharedlinkflags=["-fsycl"]
            tools.build:exelinkflags=["-fsycl"]
        """)
        client.save({"intel_profile": intel_profile})
        client.run("build . -pr:b intel_profile -pr:h intel_profile")
        assert ":: initializing oneAPI environment ..." in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        # Run executable with Intel environment active (needed for libsycl.so)
        build_folder = os.path.join(client.current_folder, "build", "Release")
        client.run_command(f'. /opt/intel/oneapi/setvars.sh --force && "{build_folder}/hello"')
        assert "Hello World" in client.out
