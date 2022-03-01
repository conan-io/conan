import os
import textwrap

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TurboTestClient


@pytest.mark.tool_autotools()
def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    client = TurboTestClient(path_with_spaces=False)
    client.run("new hello/1.0 --template cmake_lib")
    client.run("create .")
    consumer_conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            requires = "hello/1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp", "consumer.h"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def layout(self):
                self.folders.build = "."
                self.cpp.package.bindirs = ["mybin"]

            def build(self):
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
                autotools.install()
    """)

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()
    client.save({"conanfile.py": consumer_conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main}, clean_first=True)
    ref = ConanFileReference.loads("zlib/1.2.11")
    pref = client.create(ref, conanfile=consumer_conanfile)
    p_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(p_folder, "mybin", "main"))
    assert not os.path.exists(os.path.join(p_folder, "bin"))
