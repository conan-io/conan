import pytest
from pathlib import Path
import platform
import textwrap

from test.conftest import tools_locations
from conan.test.utils.tools import TestClient


SYCL_CODE = textwrap.dedent("""
    #include <sycl/sycl.hpp>
    #include <iostream>
    #include <vector>
    #include <string>

    void hello() {
        sycl::queue q;
        std::cout << "Hello World from SYCL device: "
                  << q.get_device().get_info<sycl::info::device::name>() << std::endl;
    }

    void hello_print_vector(const std::vector<std::string> &strings) {
        sycl::queue q;
        std::cout << "SYCL device: " << q.get_device().get_info<sycl::info::device::name>() << std::endl;
        for (const auto &s : strings) {
            std::cout << s << std::endl;
        }
    }
""")


@pytest.mark.tool("intel_oneapi")
@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
class TestIntelCC:
    """Tests for Intel oneAPI C++/DPC++ compilers on Linux"""

    oneapi_path = Path(tools_locations["intel_oneapi"]["2026.0"]["root"]["Linux"])

    @pytest.mark.tool("cmake")
    def test_intel_oneapi_and_icpx(self):
        """Test Intel oneAPI icx/icpx C++ compiler with CMake."""
        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=0.1")
        compiler_executables = (
            'tools.build:compiler_executables={"c": "icx-cl", "cpp": "icx-cl"}'
            if platform.system() == "Windows"
            else ""
        )

        intel_profile = textwrap.dedent(f"""
            [settings]
            os={platform.system()}
            arch=x86_64
            compiler=intel-cc
            compiler.mode=icx
            compiler.version=2026.0
            compiler.libcxx=libstdc++
            build_type=Release

            [conf]
            tools.intel:installation_path={self.oneapi_path}
            {compiler_executables}
        """)

        client.save({"intel_profile": intel_profile})
        client.run("create -pr:b intel_profile -pr:h intel_profile")
        assert ":: initializing oneAPI environment" in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World" in client.out
        assert "__INTEL_LLVM_COMPILER2026" in client.out

    intel_sycl_profile = textwrap.dedent(f"""
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
        tools.intel:installation_path={oneapi_path}
    """)

    @pytest.mark.tool("cmake")
    def test_intel_oneapi_and_sycl_cmake(self):
        """Test Intel oneAPI with SYCL using CMake."""
        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=0.1")
        client.save({"intel_profile": self.intel_sycl_profile, "src/hello.cpp": SYCL_CODE})
        client.run("create . -pr:a intel_profile")
        assert ":: initializing oneAPI environment" in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World from SYCL device" in client.out

    @pytest.mark.tool("autotools")
    def test_intel_oneapi_and_sycl_autotools(self):
        """Test Intel oneAPI with SYCL using Autotools."""
        client = TestClient(path_with_spaces=False)
        client.run("new autotools_lib -d name=hello -d version=0.1")
        client.save({"intel_profile": self.intel_sycl_profile, "src/hello.cpp": SYCL_CODE})
        client.run("create . -pr:a intel_profile")
        assert ":: initializing oneAPI environment" in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World from SYCL device" in client.out

    @pytest.mark.tool("autotools")
    def test_intel_oneapi_and_sycl_gnutoolchain(self):
        """Test Intel oneAPI with SYCL using GnuToolchain."""
        client = TestClient(path_with_spaces=False)
        client.run("new autotools_lib -d name=hello -d version=0.1")
        conanfile = client.load("conanfile.py")
        conanfile = conanfile.replace("AutotoolsToolchain", "GnuToolchain")
        client.save({"conanfile.py": conanfile, "intel_profile": self.intel_sycl_profile, "src/hello.cpp": SYCL_CODE})
        client.run("create . -pr:a intel_profile")
        assert ":: initializing oneAPI environment" in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World from SYCL device" in client.out

    @pytest.mark.tool("meson")
    def test_intel_oneapi_and_sycl_meson(self):
        """Test Intel oneAPI with SYCL using Meson."""
        client = TestClient()
        client.run("new meson_lib -d name=hello -d version=0.1")
        client.save({"intel_profile": self.intel_sycl_profile, "src/hello.cpp": SYCL_CODE})
        client.run("create . -pr:a intel_profile")
        assert ":: initializing oneAPI environment" in client.out
        assert ":: oneAPI environment initialized ::" in client.out
        assert "Hello World from SYCL device" in client.out

