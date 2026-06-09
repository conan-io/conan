import pytest
from pathlib import Path
import platform
import textwrap
import os

from test.conftest import tools_locations
from conan.test.utils.tools import TestClient


@pytest.mark.tool("intel_oneapi")
@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
class TestIntelCC:

    """Tests for Intel oneAPI C++/DPC++ compilers"""

    oneapi_path = Path(tools_locations["intel_oneapi"]["2026.0"]["root"]["Linux"])

    @pytest.mark.tool("cmake")
    def test_intel_oneapi_and_icpx(self):
        """
        Test Intel oneAPI icx/icpx C++ compiler with CMake.
        Creates a library package and verifies compilation works.
        """
        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=0.1")
        intel_profile = textwrap.dedent(f"""
            [settings]
            os=Linux
            arch=x86_64
            compiler=intel-cc
            compiler.mode=icx
            compiler.version=2026.0
            compiler.libcxx=libstdc++
            build_type=Release

            [conf]
            tools.intel:installation_path={self.oneapi_path}
        """)

        client.save({"intel_profile": intel_profile})
        client.run("create -pr:b intel_profile -pr:h intel_profile")
        assert ":: initializing oneAPI environment ..." in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World" in client.out

    @pytest.mark.tool("cmake")
    def test_intel_oneapi_and_sycl(self):
        """
        Test Intel oneAPI with SYCL support.
        DPC++ compiler (dpcpp) was deprecated in oneAPI 2024.0.
        Now SYCL code is compiled with: icpx -fsycl
        """
        client = TestClient()
        client.run("new cmake_exe -d name=hello -d version=0.1")
        intel_profile = textwrap.dedent(f"""
            [settings]
            os=Linux
            arch=x86_64
            compiler=intel-cc
            compiler.mode=icx
            compiler.version=2026.0
            compiler.libcxx=libstdc++
            build_type=Release

            [conf]
            tools.build:cxxflags=["-fsycl"]
            tools.build:exelinkflags=["-fsycl"]
            tools.build:sharedlinkflags=["-fsycl"]
            tools.intel:installation_path={self.oneapi_path}
        """)
        sycl_code = textwrap.dedent("""
            #include <sycl/sycl.hpp>
            int main() {
                sycl::range<1> r{1};
                return r.size() == 1 ? 0 : 1;
            }
        """)

        client.save({"intel_profile": intel_profile, "src/main.cpp": sycl_code})
        client.run("build . -pr:b intel_profile -pr:h intel_profile")
        assert ":: initializing oneAPI environment ..." in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        # Run executable with Intel environment active (needed for libsycl.so)
        build_folder = os.path.join(client.current_folder, "build", "Release")
        client.run_command(f'. {self.oneapi_path}/setvars.sh --force && "{build_folder}/hello"')

    def test_intel_oneapi_autotools(self):
        client = TestClient(path_with_spaces=False)
        client.run("new autotools_exe -d name=hello -d version=0.1")
        intel_profile = textwrap.dedent(f"""
           [settings]
           os=Linux
           arch=x86_64
           compiler=intel-cc
           compiler.mode=icx
           compiler.version=2026.0
           compiler.libcxx=libstdc++
           build_type=Release

           [conf]
           tools.build:compiler_executables={{'c': 'icx', 'cpp': 'icpx'}}
           tools.intel:installation_path={self.oneapi_path}
           """)

        client.save({"intel_profile": intel_profile})
        client.run("create -pr:h intel_profile -c tools.compilation:verbosity=verbose")
        assert ":: initializing oneAPI environment ..." in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World" in client.out
        assert "hello/0.1: __INTEL_LLVM_COMPILER2026" in client.out
