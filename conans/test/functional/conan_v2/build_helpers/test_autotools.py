import textwrap
import platform

import pytest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


@pytest.mark.skipif(platform.system() != "Linux", reason="Requires make")
@pytest.mark.tool_autotools
class AutotoolsBuildHelperTestCase(ConanV2ModeTestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, AutoToolsBuildEnvironment, tools

        class Pkg(ConanFile):
            settings = "os", "arch", "{}"
            exports_sources = "main.cpp"
            def build(self):
                makefile_am = '''
        bin_PROGRAMS = main
        main_SOURCES = main.cpp
        '''
                configure_ac = '''
        AC_INIT([main], [1.0], [luism@jfrog.com])
        AM_INIT_AUTOMAKE([-Wall -Werror foreign])
        AC_PROG_CXX
        AC_PROG_RANLIB
        AM_PROG_AR
        AC_CONFIG_FILES([Makefile])
        AC_OUTPUT
        '''
                tools.save("Makefile.am", makefile_am)
                tools.save("configure.ac", configure_ac)
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = AutoToolsBuildEnvironment(self)
                autotools.configure()
                autotools.make()
    """)

    main_cpp = textwrap.dedent("""\
        int main(){{
            return 0;
        }}
    """)

    def test_no_build_type(self):
        t = self.get_client()
        t.save({"conanfile.py": self.conanfile.format("compiler"), "main.cpp": self.main_cpp})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: build_type setting should be defined.", t.out)

    def test_no_compiler(self):
        t = self.get_client()
        t.save({"conanfile.py": self.conanfile.format("build_type"), "main.cpp": self.main_cpp})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: compiler setting should be defined.", t.out)
