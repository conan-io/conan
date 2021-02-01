import os
import platform
import textwrap

import pytest

from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


#@pytest.mark.skipif(platform.system() != "Linux", reason="Requires Autotools")
#@pytest.mark.tool_autotools()
def test_autotools():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=v2_cmake")
    client.run("create .")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools, AutotoolsDeps
        from conans.tools import environment_append

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "*"

            def generate(self):
                deps = AutotoolsDeps(self)
                deps.generate()
                #tc = AutotoolsToolchain(self)
                #tc.generate()

            def build(self):
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
                autotools.install()
        """)

    client.save({"conanfile.py": conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main}, clean_first=True)
    print(client.current_folder)
    client.run("install .")
    print(client.load("conandeps.sh"))
    client.run("build .")
    print(os.listdir(client.current_folder))
    client.run_command("./main")
    assert "hello/0.1: Hello World Release!" in client.out
