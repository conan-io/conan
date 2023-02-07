import os
import platform
import textwrap

import pytest

from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp
from conans.test.conftest import tools_locations
from conans.test.functional.utils import check_exe_run
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.xfail(reason="Winbash is broken for multi-profile. Ongoing https://github.com/conan-io/conan/pull/9755")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("msys2")
def test_autotools_bash_complete():
    client = TestClient(path_with_spaces=False)
    bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
    save(client.cache.new_config_path, textwrap.dedent("""
            tools.microsoft.bash:subsystem=msys2
            tools.microsoft.bash:path={}
            tools.build:compiler_executables={{"c": "cl", "cpp": "cl"}}
            """.format(bash_path)))

    main = gen_function_cpp(name="main")
    # The autotools support for "cl" compiler (VS) is very limited, linking with deps doesn't
    # work but building a simple app do
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsToolchain"
            win_bash = True

            def build(self):
                # These commands will run in bash activating first the vcvars and
                # then inside the bash activating the
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
                 "main.cpp": main})
    client.run("install . -s:b os=Windows -s:h os=Windows")
    client.run("build .")
    client.run_command("main.exe")
    check_exe_run(client.out, "main", "msvc", None, "Release", "x86_64", None)

    bat_contents = client.load("conanbuild.bat")
    assert "conanvcvars.bat" in bat_contents

    # To check that the ``autotools.install()`` has worked correctly
    # FIXME IN CONAN 2.0 this will break, no local `package_folder`
    assert os.path.exists(os.path.join(client.current_folder, "package", "bin", "main.exe"))


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_add_msys2_path_automatically():
    """ Check that commands like ar, autoconf, etc, that are in the /usr/bin folder together
    with the bash.exe, can be automaticallly used when running in windows bash, without user
    extra addition to [buildenv] of that msys64/usr/bin path

    # https://github.com/conan-io/conan/issues/12110
    """
    client = TestClient(path_with_spaces=False)
    bash_path = None
    try:
        bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
    except KeyError:
        pytest.skip("msys2 path not defined")

    save(client.cache.new_config_path, textwrap.dedent("""
            tools.microsoft.bash:subsystem=msys2
            tools.microsoft.bash:path={}
            """.format(bash_path)))

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            win_bash = True

            def build(self):
                self.run("ar -h")
                """)

    client.save({"conanfile.py": conanfile})
    client.run("create .")
    assert "ar.exe" in client.out
