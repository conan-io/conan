import os
import textwrap

from conans.model.ref import ConanFileReference
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TurboTestClient


def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    client = TurboTestClient()
    client.run("new hello/1.0 --template cmake-lib")
    client.run("create .")
    consumer_conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            requires = "hello/1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def layout(self):
                self.folders.build = "."

            def build(self):
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
                autotools.install()
    """)

    main = gen_function_cpp(name="consumer", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()
    client.save({"conanfile.py": consumer_conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main}, clean_first=True)
    ref = ConanFileReference.loads("zlib/1.2.11")
    client.create(ref, conanfile=consumer_conanfile)


