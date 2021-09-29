import pytest
import platform
import textwrap

from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
@pytest.mark.tool_intel_oneapi
@pytest.mark.xfail(reason="Intel oneAPI Toolkit is not installed on CI yet")
@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
class TestInteloneAPI:

    @pytest.fixture(autouse=True)
    def _setUp(self):
        conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake
        from conan.tools.layout import cmake_layout


        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False]}
            default_options = {"shared": False}

            # Sources are located in the same place as this recipe, copy them to the recipe
            exports_sources = "CMakeLists.txt", "src/*"

            def layout(self):
                cmake_layout(self)

            def generate(self):
                tc = CMakeToolchain(self)
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ["hello"]
            """)
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", includes=["hello"])
        cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(hello CXX)

        add_library(hello src/hello.cpp)

        set_target_properties(hello PROPERTIES PUBLIC_HEADER "src/hello.h")
        install(TARGETS hello DESTINATION "."
                PUBLIC_HEADER DESTINATION include
                RUNTIME DESTINATION bin
                ARCHIVE DESTINATION lib
                LIBRARY DESTINATION lib
                )
        """)
        self.client = TestClient()
        self.client.save({
            "conanfile.py": conanfile,
            "CMakeLists.txt": cmakelist,
            "src/hello.h": hello_h,
            "src/hello.cpp": hello_cpp,
        })

    def test_intel_oneapi_and_dpcpp(self):
        intel_profile = textwrap.dedent("""
            [settings]
            os=Linux
            arch=x86_64
            arch_build=x86_64
            compiler=intel-cc
            compiler.mode=dpcpp
            compiler.version=2021.3
            compiler.libcxx=libstdc++
            build_type=Release
            [env]
            CC=dpcpp
            CXX=dpcpp
        """)
        self.client.save({"intel_profile": intel_profile})
        # Build in the cache
        self.client.run('create . --profile:build=intel_profile --profile:host=intel_profile')
        assert ":: initializing oneAPI environment ..." in self.client.out
        assert ":: oneAPI environment initialized ::" in self.client.out
        assert "Check for working CXX compiler: /opt/intel/oneapi/compiler/2021.3.0/linux/bin/dpcpp -- works" in self.client.out
        assert "hello/0.1: Package '5d42bcd2e9be3378ed0c2f2928fe6dc9ea1b0922' created" in self.client.out
