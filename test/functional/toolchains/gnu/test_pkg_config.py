import platform
import textwrap

import pytest

from test.conftest import tools_locations
from conan.test.utils.tools import TestClient
from conan.test.utils.env import environment_update


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
        assert "PkgConfig failed. Command: pkg-config --libs-only-l something_that_not_exist " \
               "--print-errors" in c.out
        assert "Package something_that_not_exist was not found" in c.out

    def test_pc(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import PkgConfig
            from conan.tools import CppInfo

            class Pkg(ConanFile):
                def generate(self):
                    pkg_config = PkgConfig(self, "libastral", pkg_config_path=".")
                    self.output.info(f"PROVIDES: {pkg_config.provides}")
                    self.output.info(f"VERSION: {pkg_config.version}")
                    self.output.info(f"VARIABLES: {pkg_config.variables['prefix']}")

                    cpp_info = CppInfo(self)
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
        assert "PROVIDES: libastral = 6.6.6" in c.out
        assert "VERSION: 6.6.6" in c.out
        assert "VARIABLES: /usr/local" in c.out


def test_pkg_config_round_trip_cpp_info():
    """ test that serialize and deserialize CppInfo works
    """
    try:
        version = tools_locations["pkg_config"]["default"]
        exe = tools_locations["pkg_config"]["exe"]
        os_ = platform.system()
        pkg_config_path = tools_locations["pkg_config"][version]["path"][os_] + "/" + exe
    except KeyError:
        pytest.skip("pkg-config path not defined")  # pragma: no cover

    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.gnu import PkgConfig
        from conan.tools import CppInfo

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            exports_sources = "*.pc"

            def package(self):
                pkg_config = PkgConfig(self, "libastral", pkg_config_path=".")
                cpp_info = CppInfo(self)
                pkg_config.fill_cpp_info(cpp_info, is_system=False, system_libs=["m"])
                cpp_info.save(os.path.join(self.package_folder, "cpp_info.json"))

            def package_info(self):
                self.cpp_info = CppInfo(self).load("cpp_info.json")
        """)
    prefix = "C:" if platform.system() == "Windows" else ""
    libastral_pc = textwrap.dedent("""\
        PC FILE EXAMPLE:

        prefix=%s/usr/local
        exec_prefix=${prefix}
        libdir=${exec_prefix}/lib
        includedir=${prefix}/include

        Name: libastral
        Description: Interface library for Astral data flows
        Version: 6.6.6
        Libs: -L${libdir}/libastral -lastral -lm -Wl,--whole-archive
        Cflags: -I${includedir}/libastral -D_USE_LIBASTRAL
        """ % prefix)
    c.save({"conanfile.py": conanfile,
            "libastral.pc": libastral_pc,
            "profile": f"[conf]\ntools.gnu:pkg_config={pkg_config_path}"})
    c.run("export .")
    c.run("install --requires=pkg/0.1 -pr=profile -g CMakeDeps --build=missing")
    pkg_data = c.load("pkg-none-data.cmake")
    assert 'set(pkg_DEFINITIONS_NONE "-D_USE_LIBASTRAL")' in pkg_data
    assert 'set(pkg_SHARED_LINK_FLAGS_NONE "-Wl,--whole-archive")' in pkg_data
    assert 'set(pkg_COMPILE_DEFINITIONS_NONE "_USE_LIBASTRAL")' in pkg_data
    assert 'set(pkg_LIBS_NONE astral)' in pkg_data
    assert 'set(pkg_SYSTEM_LIBS_NONE m)' in pkg_data
    # paths
    assert f'set(pkg_INCLUDE_DIRS_NONE "{prefix}/usr/local/include/libastral")' in pkg_data
    assert f'set(pkg_LIB_DIRS_NONE "{prefix}/usr/local/lib/libastral")' in pkg_data


@pytest.mark.tool("pkg_config")
@pytest.mark.tool("msys2")
@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows PKG_CONFIG_PATH only")
def test_windows_pkg_config_path():
    """ Test pkg-config with MSYS2 on Windows mixing paths style for PKG_CONFIG_PATH

        The test creates a dummy .pc file and checks if pkg-config can find it. It should work
        for unix path style or forward slashes in Windows only. Mixing backslashes and forward slashes
        in the same path is not supported by pkg-config.

        https://www.msys2.org/docs/pkgconfig/#syntax-paths-escaping
    """

    try:
        version = tools_locations["pkg_config"]["default"]
        exe = tools_locations["pkg_config"]["exe"]
        os_ = platform.system()
        pkg_config_path = tools_locations["pkg_config"][version]["path"][os_] + "/" + exe
    except KeyError:
        pytest.skip("pkg-config path not defined")
        return

    try:
        bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
    except KeyError:
        pytest.skip("msys2 path not defined")
        return

    client = TestClient(path_with_spaces=False)
    current_folder = client.current_folder.replace("\\", "/").replace("C:", "/c")

    libfoo_pc = textwrap.dedent("""\
            libdir=/c/lib
            includedir=/c/include

            Name: libfoo
            Description: Dummy library for testing pkg-config
            Version: 0.1.0
            Libs: -L${libdir}/libfoo -lfoo -lm -Wl,--whole-archive
            Cflags: -I${includedir}/libfoo -D_USE_LIBFOO
            """)
    conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.gnu import PkgConfig
            from conan.tools.env import VirtualBuildEnv
            import os

            class TestPkg(ConanFile):
                name = "test_pkg_config"
                version = "0.1.0"
                exports_sources = "*.pc"

                def package(self):
                    pkg_config = PkgConfig(self, "libfoo", pkg_config_path="{current_folder}")
                    self.output.info(f"PROVIDES: {{pkg_config.provides}}")
            """)
    profile = textwrap.dedent(f"""
            [conf]
            tools.gnu:pkg_config={pkg_config_path}
            tools.microsoft.bash:subsystem=msys2
            tools.microsoft.bash:path={bash_path}
            tools.microsoft.bash:active=True
            """)

    client.save({"conanfile.py": conanfile,
                 "libfoo.pc": libfoo_pc,
                 "profile": profile})
    client.run("export .")

    # Test using unix path style for PKG_CONFIG_PATH
    # Expected PKG_CONFIG_PATH=/c/<current_folder>:/c/msys64/usr/lib/pkgconfig
    with environment_update({"PKG_CONFIG_PATH": "/c/msys64/usr/lib/pkgconfig"}):
        client.run("install --requires=test_pkg_config/0.1.0 -pr profile --build=missing")
        assert "PROVIDES: libfoo = 0.1.0" in str(client.out)

    # Test using forward slashes in PKG_CONFIG_PATH
    # Expected PKG_CONFIG_PATH=/c/<current_folder>:C:/msys64/usr/lib/pkgconfig
    with environment_update({"PKG_CONFIG_PATH": "C:/msys64/usr/lib/pkgconfig"}):
        client.run("install --requires=test_pkg_config/0.1.0 -pr profile --build=missing")
        assert "PROVIDES: libfoo = 0.1.0" in str(client.out)

    # Test using mixed path styles (should fail)
    # Expected PKG_CONFIG_PATH=/c/<current_folder>:C:\msys64\usr\lib\pkgconfig
    with environment_update({"PKG_CONFIG_PATH": r"C:\msys64\usr\lib\pkgconfig"}):
        client.run("install --requires=test_pkg_config/0.1.0 -pr profile --build=missing", assert_error=True)
