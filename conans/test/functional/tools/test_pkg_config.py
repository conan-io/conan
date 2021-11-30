import os

import pytest

from conan.tools.gnu.pkgconfig import PkgConfig
from conans.errors import ConanException
from conans.model.new_build_info import NewCppInfo
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
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


@pytest.mark.tool_pkg_config
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

        cpp_info = NewCppInfo()
        pkg_config.fill_cpp_info(cpp_info, is_system=False, system_libs=["m"])

        assert cpp_info.includedirs == ['/usr/local/include/libastral']
        assert cpp_info.defines == ['_USE_LIBASTRAL']
        assert cpp_info.libs == ['astral']
        assert cpp_info.system_libs == ['m']
        assert cpp_info.libdirs == ['/usr/local/lib/libastral']
        assert cpp_info.sharedlinkflags == ['-Wl,--whole-archive']
