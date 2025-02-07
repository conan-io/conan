import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("pkg_config")
@pytest.mark.tool("autotools")
@pytest.mark.skipif(platform.system() == "Windows", reason="Needs pkg-config")
def test_pkgconfigdeps_and_autotools():
    """
    This test aims to show how to use PkgConfigDeps and AutotoolsToolchain.

    In this case, the test_package is using PkgConfigDeps and AutotoolsToolchain to use
    the created pkg/1.0 package. It's important to make a full compilation to ensure that
    the test main.cpp is using correctly the flags passed via pkg.pc file.

    Issue related: https://github.com/conan-io/conan/issues/11867
    """
    client = TestClient(path_with_spaces=False)
    conanfile_pkg = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.gnu import Autotools
    from conan.tools.layout import basic_layout
    from conan.tools.apple import fix_apple_shared_install_name


    class PkgConan(ConanFile):
        name = "pkg"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}
        exports_sources = "configure.ac", "Makefile.am", "src/*"
        generators = "AutotoolsToolchain"

        def layout(self):
            basic_layout(self)

        def build(self):
            autotools = Autotools(self)
            autotools.autoreconf()
            autotools.configure()
            autotools.make()

        def package(self):
            autotools = Autotools(self)
            autotools.install()
            fix_apple_shared_install_name(self)

        def package_info(self):
            self.cpp_info.libs = ["pkg"]
            # Add non-existing frameworkdirs to check that it's not failing because of this
            self.cpp_info.frameworkdirs = ["/my/framework/file1", "/my/framework/file2"]
    """)
    conanfile_test = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.gnu import Autotools
    from conan.tools.layout import basic_layout
    from conan.tools.build import cross_building
    class PkgTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "PkgConfigDeps", "AutotoolsToolchain"

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            autotools = Autotools(self)
            autotools.autoreconf()
            autotools.configure()
            autotools.make()

        def layout(self):
            basic_layout(self)

        def test(self):
            if not cross_building(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "main")
                self.run(cmd, env="conanrun")
    """)
    configure_test = textwrap.dedent("""
    AC_INIT([main], [1.0], [])
    AM_INIT_AUTOMAKE([-Wall -Werror foreign])
    AC_PROG_CXX
    PKG_PROG_PKG_CONFIG
    PKG_CHECK_MODULES([pkg], [pkg >= 1.0])
    AC_CONFIG_FILES([Makefile])
    AC_OUTPUT
    """)
    makefile_test = textwrap.dedent("""
    bin_PROGRAMS = main
    main_SOURCES = main.cpp
    AM_CXXFLAGS = $(pkg_CFLAGS)
    main_LDADD = $(pkg_LIBS)
    """)
    client.run("new autotools_lib -d name=pkg -d version=1.0")
    client.save({"conanfile.py": conanfile_pkg,
                 "test_package/conanfile.py": conanfile_test,
                 "test_package/configure.ac": configure_test,
                 "test_package/Makefile.am": makefile_test,
                 })
    # client.run("new autotools_lib -d name=pkg -d version=1.0")
    client.run("create .")
    if platform.system() == "Darwin":
        # Checking that frameworkdirs appear all together instead of "-F /whatever/f1"
        # Issue: https://github.com/conan-io/conan/issues/11867
        assert '-F/my/framework/file1' in client.out
        assert '-F/my/framework/file2' in client.out
