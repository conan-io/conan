import os
import platform
import textwrap
import time

import pytest

from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_exe_run
from conans.test.utils.tools import TestClient
from conans.util.files import touch


@pytest.mark.skipif(platform.system() != "Linux", reason="Requires Autotools")
@pytest.mark.tool_autotools()
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

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "*"

            def generate(self):
                deps = AutotoolsDeps(self)
                deps.generate()
                tc = AutotoolsToolchain(self)
                tc.generate()

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
    client.run("install .")
    client.run("build .")
    client.run_command("./main")
    check_exe_run(client.out, "main", "gcc", None, "Release", "x86_64", None)
    assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for Mingw")
def test_autotoolsdeps_mingw():
    """ The AutotoolsDeps can be used also in pure Makefiles, if the makefiles follow
    the Autotools conventions
    """
    client = TestClient()
    client.run("new hello/0.1 --template=v2_cmake")
    gcc = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=gcc
        compiler.version=4.9
        compiler.libcxx=libstdc++
        arch=x86_64
        build_type=Release
        """)
    client.save({"profile_gcc": gcc})
    client.run("create . --profile=profile_gcc")
    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile = textwrap.dedent("""\
        app: main.o
        	$(CXX) $(CFLAGS) $(LDFLAGS) -o app main.o $(LIBS)

        main.o: main.cpp
        	$(CXX) $(CFLAGS) $(CXXFLAGS) $(CPPFLAGS) -c -o main.o main.cpp
        """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools, AutotoolsDeps

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "Makefile"

            def generate(self):
                deps = AutotoolsDeps(self)
                deps.generate()
                tc = AutotoolsToolchain(self)
                tc.generate()

            def build(self):
                autotools = Autotools(self)
                autotools.make()
        """)
    client.save({"main.cpp": main,
                 "Makefile": makefile,
                 "conanfile.py": conanfile,
                 "profile_gcc": gcc}, clean_first=True)

    client.run("install . --profile=profile_gcc")
    client.run_command("autotoolsdeps.bat && autotools.bat && mingw32-make")
    client.run_command("app")
    # TODO: fill compiler version when ready
    check_exe_run(client.out, "main", "gcc", None, "Release", "x86_64", None)
    assert "hello/0.1: Hello World Release!" in client.out

    client.save({"main.cpp": gen_function_cpp(name="main", msg="main2",
                                              includes=["hello"], calls=["hello"])})
    # Make sure it is newer
    t = time.time() + 1
    touch(os.path.join(client.current_folder, "main.cpp"), (t, t))

    client.run("build .")
    client.run_command("app")
    # TODO: fill compiler version when ready
    check_exe_run(client.out, "main2", "gcc", None, "Release", "x86_64", None)
    assert "hello/0.1: Hello World Release!" in client.out
