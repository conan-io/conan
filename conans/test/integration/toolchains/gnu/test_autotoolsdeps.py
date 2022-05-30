import platform
import re
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Autotools")
def test_link_lib_correct_order():
    client = TestClient()
    liba = GenConanfile().with_name("liba").with_version("0.1")
    libb = GenConanfile().with_name("libb").with_version("0.1").with_require("liba/0.1")
    libc = GenConanfile().with_name("libc").with_version("0.1").with_require("libb/0.1")
    consumer = GenConanfile().with_require("libc/0.1")
    client.save({"liba.py": liba, "libb.py": libb, "libc.py": libc, "consumer.py": consumer})
    client.run("create liba.py")
    client.run("create libb.py")
    client.run("create libc.py")
    client.run("install consumer.py -g AutotoolsDeps")
    deps = client.load("conanautotoolsdeps.sh")
    # check the libs are added in the correct order with this regex
    assert re.search("export LDFLAGS.*libc.*libb.*liba", deps)


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Autotools")
def test_cpp_info_aggregation():

    profile = textwrap.dedent("""
         [settings]
         build_type=Release
         arch=x86
         os=Macos
         compiler=gcc
         compiler.libcxx=libstdc++11
         compiler.version=7.1
         cppstd=17
    """)

    dep_conanfile = textwrap.dedent("""

    from conan import ConanFile

    class Dep(ConanFile):

        settings = "os", "arch", "compiler", "build_type"

        def package_info(self):
            self.cpp_info.includedirs = []
            self.cpp_info.includedirs.append("path/includes/{}".format(self.name))
            self.cpp_info.includedirs.append("other\\include\\path\\{}".format(self.name))
            # To test some path in win, to be used with MinGW make or MSYS etc
            self.cpp_info.libdirs = []
            self.cpp_info.libdirs.append("one\\lib\\path\\{}".format(self.name))
            self.cpp_info.libs = []
            self.cpp_info.libs.append("{}_onelib".format(self.name))
            self.cpp_info.libs.append("{}_twolib".format(self.name))
            self.cpp_info.defines = []
            self.cpp_info.defines.append("{}_onedefinition".format(self.name))
            self.cpp_info.defines.append("{}_twodefinition".format(self.name))
            self.cpp_info.cflags = ["{}_a_c_flag".format(self.name)]
            self.cpp_info.cxxflags = ["{}_a_cxx_flag".format(self.name)]
            self.cpp_info.sharedlinkflags = ["{}_shared_link_flag".format(self.name)]
            self.cpp_info.exelinkflags = ["{}_exe_link_flag".format(self.name)]
            self.cpp_info.sysroot = "/path/to/folder/{}".format(self.name)
            self.cpp_info.frameworks = []
            self.cpp_info.frameworks.append("{}_oneframework".format(self.name))
            self.cpp_info.frameworks.append("{}_twoframework".format(self.name))
            self.cpp_info.system_libs = []
            self.cpp_info.system_libs.append("{}_onesystemlib".format(self.name))
            self.cpp_info.system_libs.append("{}_twosystemlib".format(self.name))
            self.cpp_info.frameworkdirs = []
            self.cpp_info.frameworkdirs.append("one/framework/path/{}".format(self.name))

    """)

    t = TestClient()
    t.save({"conanfile.py": dep_conanfile, "macos": profile})
    t.run("create . dep1/1.0@ --profile:host=macos")
    t.run("create . dep2/1.0@ --profile:host=macos")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsDeps

        class HelloConan(ConanFile):
            generators = "AutotoolsDeps"
            requires = "dep1/1.0", "dep2/1.0"
            settings = "os", "arch", "build_type", "compiler"

            def generate(self):
                deps = AutotoolsDeps(self)
                env = deps.environment

                # Customize the environment
                env.remove("LDFLAGS", "dep2_shared_link_flag")
                env.append("LDFLAGS", "OtherSuperStuff")

                env = deps.vars()
                # The contents are of course modified
                self.output.warn(env["CXXFLAGS"])

                # The topological order puts dep2 before dep1
                assert env["CXXFLAGS"] == 'dep2_a_cxx_flag dep1_a_cxx_flag'
                assert env["CFLAGS"] == 'dep2_a_c_flag dep1_a_c_flag'
                assert env["LIBS"] == "-ldep2_onelib -ldep2_twolib -ldep1_onelib -ldep1_twolib "\
                                      "-ldep2_onesystemlib -ldep2_twosystemlib "\
                                      "-ldep1_onesystemlib -ldep1_twosystemlib"

                assert env["LDFLAGS"].startswith('dep1_shared_link_flag dep2_exe_link_flag dep1_exe_link_flag -framework dep2_oneframework -framework dep2_twoframework ' \
                                     '-framework dep1_oneframework -framework dep1_twoframework ')
                assert 'OtherSuperStuff' in env["LDFLAGS"]
    """)

    t.save({"conanfile.py": consumer})
    t.run("create . consumer/1.0@ --profile:host=macos")
