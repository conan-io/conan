import platform
import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.fixture
def client():
    c = TestClient()
    save(c.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
    clang_profile = textwrap.dedent("""
        [settings]
        arch=armv7
        build_type=RelWithDebInfo
        compiler=clang
        compiler.libcxx=libstdc++11
        compiler.version=12
        os=VxWorks
        os.version=7

        [buildenv]
        CC=clang
        CXX=clang++
        """)
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                cmd = os.path.join(self.cpp.build.bindirs[0], "my_app")
                self.run('readelf -s ' + cmd, env=["conanrunenv"])
        """)
    toolchain_file = textwrap.dedent("""
            set(vsb "/vsb") # location of VxWorks Source Build (vsb)
            set(CMAKE_LINKER "ldarm")
            set(CMAKE_CXX_LINK_EXECUTABLE "<CMAKE_LINKER> <CMAKE_CXX_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET> <LINK_LIBRARIES>" CACHE STRING "Workaround for clang, use GNU linker not clang/lld" FORCE)
            set(CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES
                ${vsb}/usr/h
                ${vsb}/usr/h/public
                ${vsb}/h/config
                ${vsb}/share/h/public
            )
            add_compile_definitions(
                ARMEL
                CPU=_VX_ARMARCH7
                _REENTRANT
                INET
                _VSB_CONFIG_FILE="${vsb}/h/config/vsbConfig.h"
            )
            add_compile_options(
                -fno-builtin
                -pipe
            )
            add_compile_definitions(
                _C99
                _HAS_C9X
                _VX_CPU=_VX_ARMARCH7
                __RTP__
                TOOL=llvm
                TOOL_FAMILY=llvm
                CPU_FAMILY=ARM
                __ELF__
                __vxworks
                __VXWORKS__
                _USE_INIT_ARRAY
            )
            add_compile_options(
                -fasm
                -fomit-frame-pointer
                -ffunction-sections
                -fdata-sections
                --target=arm-eabi
                -mabi=aapcs
                -mcpu=cortex-a9
                -mfloat-abi=hard
                -mfpu=vfpv3
                -mlittle-endian
                -mno-implicit-float
                -nostdinc++
                -nostdlibinc
                -march=armv7
                -gdwarf-3
                -mllvm
                -two-entry-phi-node-folding-threshold=2
            )
            add_link_options(
                --target2=rel
            )
            link_directories(
                ${vsb}/usr/lib/common
            )

            set(CMAKE_CXX_STANDARD 14)
            set(CMAKE_C_STANDARD_LIBRARIES "--start-group --as-needed -lllvm -lc -lc_internal --end-group")
            set(CMAKE_CXX_STANDARD_LIBRARIES "-lnet --start-group --as-needed -lc -lc_internal -lllvm -lcplusplus -lllvmcplus -ldl --end-group")
            set(CMAKE_EXE_LINKER_FLAGS "--defsym __wrs_rtp_base=0x80000000 -u __wr_need_frame_add -u __tls__ -T${vsb}/usr/ldscripts/rtp.ld -static -EL ${vsb}/usr/lib/common/crt0.o" CACHE STRING "" FORCE)
        """)
    c.save({"conanfile.py": conanfile,
            "clang": clang_profile,
            "toolchain-vxworks.cmake": toolchain_file,
            "CMakeLists.txt": gen_cmakelists(appname="my_app", appsources=["src/main.cpp"]),
            "src/main.cpp": gen_function_cpp(name="main")})
    return c


@pytest.mark.tool_cmake
@pytest.mark.tool_clang(version="12")
def test_clang_cmake_ninja(client):
    client.run("create . pkg/0.1@ -pr=clang -c tools.cmake.cmaketoolchain:generator=Ninja -c tools.cmake.cmaketoolchain:toolchain_file=../../toolchain-vxworks.cmake")
    assert 'cmake -G "Ninja"' in client.out
    assert "__wrs_rtp_" in client.out
