import os
import platform
import textwrap

import pytest

from conan.tools.gnu.pkgconfig import PkgConfig
from conans.errors import ConanException
from conans.model.build_info import CppInfo
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save

libastral_pc = """
PC FILE EXAMPLE:

prefix=/usr/local
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: libastral
Description: Interface library for Astral data flows
Version: 6.6.6
Libs: -L${libdir}/libastral -lastral -lm -Wl,--whole-archive
Cflags: -I${includedir}/libastral -D_USE_LIBASTRAL
"""


@pytest.mark.tool("pkg_config")
class TestPkgConfig:
    def test_negative(self):
        conanfile = ConanFileMock()
        pkg_config = PkgConfig(conanfile, 'libsomething_that_does_not_exist_in_the_world')
        with pytest.raises(ConanException):
            pkg_config.libs()

    def test_pc(self):
        tmp_dir = temp_folder()
        filename = os.path.join(tmp_dir, 'libastral.pc')
        save(filename, libastral_pc)

        conanfile = ConanFileMock()
        pkg_config = PkgConfig(conanfile, "libastral", pkg_config_path=tmp_dir)

        assert pkg_config.provides == "libastral = 6.6.6"
        assert pkg_config.version == "6.6.6"
        assert pkg_config.includedirs == ['/usr/local/include/libastral']
        assert pkg_config.defines == ['_USE_LIBASTRAL']
        assert pkg_config.libs == ['astral', 'm']
        assert pkg_config.libdirs == ['/usr/local/lib/libastral']
        assert pkg_config.linkflags == ['-Wl,--whole-archive']
        assert pkg_config.variables['prefix'] == '/usr/local'

        cpp_info = CppInfo()
        pkg_config.fill_cpp_info(cpp_info, is_system=False, system_libs=["m"])

        assert cpp_info.includedirs == ['/usr/local/include/libastral']
        assert cpp_info.defines == ['_USE_LIBASTRAL']
        assert cpp_info.libs == ['astral']
        assert cpp_info.system_libs == ['m']
        assert cpp_info.libdirs == ['/usr/local/lib/libastral']
        assert cpp_info.sharedlinkflags == ['-Wl,--whole-archive']


def test_pkg_config_path():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import PkgConfig
        from conans.model.build_info import CppInfo

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def package(self):
                pkg_config = PkgConfig(self, "egl")
                cpp_info = CppInfo()
                cpp_info.includedirs = pkg_config.includedirs
                cpp_info.save(self.package_folder)

            def package_info(self):
                cpp_info = CppInfo.load()
                self.cpp_info = cpp_info
                self.output.info(f"INFO INCLUDEDIRS {self.cpp_info.includedirs}")
        """)
    profile = textwrap.dedent("""
        [buildenv]
        PKG_CONFIG_PATH=(path)/my/pkg/config/path
        """)
    c.save({"conanfile.py": conanfile,
            "mypkgconf.bat": "@echo off\necho -I%PKG_CONFIG_PATH%",
            "mypkgconf.sh": "printenv PKG_CONFIG_PATH",
            "profile": profile})
    mypkgconf = "mypkgconf.bat" if platform.system() == "Windows" else "mypkgconf.sh"
    mypkgconf = os.path.join(c.current_folder, mypkgconf)
    c.run(f'create . -pr=profile -c tools.gnu:pkg_config="{mypkgconf}"')
    assert "pkg/0.1: INFO INCLUDEDIRS ['/my/pkg/config/path']" in c.out
