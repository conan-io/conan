import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool("pkg_config")
class TestPkgConfig:
    """ This test uses the pkg_config in the system
    """
    def test_negative(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import PkgConfig

            class Pkg(ConanFile):
                def generate(self):
                    pkg_config = PkgConfig(self, "something_that_not_exist")
                    pkg_config.libs
                """)
        c.save({"conanfile.py": conanfile})
        c.run("install .", assert_error=True)
        assert "Package something_that_not_exist was not found" in c.out

    def test_pc(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import PkgConfig
            from conans.model.build_info import CppInfo

            class Pkg(ConanFile):
                def generate(self):
                    pkg_config = PkgConfig(self, "libastral", pkg_config_path=".")
                    self.output.info(f"PROVIDES: {pkg_config.provides}")
                    self.output.info(f"VERSION: {pkg_config.version}")
                    self.output.info(f"VARIABLES: {pkg_config.variables['prefix']}")

                    cpp_info = CppInfo()
                    pkg_config.fill_cpp_info(cpp_info, is_system=False, system_libs=["m"])

                    assert cpp_info.includedirs == ['/usr/local/include/libastral']
                    assert cpp_info.defines == ['_USE_LIBASTRAL']
                    assert cpp_info.libs == ['astral']
                    assert cpp_info.system_libs == ['m']
                    assert cpp_info.libdirs == ['/usr/local/lib/libastral']
                    assert cpp_info.sharedlinkflags == ['-Wl,--whole-archive']
            """)
        libastral_pc = textwrap.dedent("""\
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
            """)
        c.save({"conanfile.py": conanfile,
                "libastral.pc": libastral_pc})
        c.run("install .")
        assert "conanfile.py: PROVIDES: libastral = 6.6.6" in c.out
        assert "conanfile.py: VERSION: 6.6.6" in c.out
        assert "conanfile.py: VARIABLES: /usr/local" in c.out
