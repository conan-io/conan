import os
import platform
import textwrap

import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.sources import gen_function_cpp
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


@pytest.fixture
def client():
    # We use special characters and spaces, to check everything works
    # https://github.com/conan-io/conan/issues/12648
    # FIXME: This path still fails the creation of the deactivation script
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += """

    def package_info(self):
        self.buildenv_info.define_path("MYPATH1", "c:/path/to/ar")
        self.runenv_info.define("MYVAR1", 'some nice content\" with quotes')
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:powershell=True\n")
    return client


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows powershell")
def test_virtualenv(client):
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class ConanFileToolsTest(ConanFile):
            name = "app"
            version = "0.1"
            requires = "pkg/0.1"
            apply_env = False

            def build(self):
                self.output.info("----------BUILD----------------")
                self.run("set")
                self.output.info("----------RUN----------------")
                self.run("set", env="conanrun")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Windows")

    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.bat"))
    with open(os.path.join(client.current_folder, "conanbuildenv.ps1"), "r", encoding="utf-16") as f:
        buildenv = f.read()
    assert '$env:MYPATH1="c:/path/to/ar"' in buildenv
    build = client.load("conanbuild.ps1")
    assert "conanbuildenv.ps1" in build

    with open(os.path.join(client.current_folder, "conanrunenv.ps1"), "r", encoding="utf-16") as f:
        run_contents = f.read()
    assert '$env:MYVAR1="some nice content`" with quotes"' in run_contents

    client.run("create .")
    assert "MYPATH1=c:/path/to/ar" in client.out
    assert 'MYVAR1=some nice content" with quotes' in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows powershell")
def test_virtualenv_test_package():
    """ The test_package could crash if not cleaning correctly the test_package
    output folder. This will still crassh if the layout is not creating different build folders
    https://github.com/conan-io/conan/issues/12764
    """
    client = TestClient()
    test_package = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.files import save
        class Test(ConanFile):
            def requirements(self):
                self.requires(self.tested_reference_str)
            def generate(self):
                # Emulates vcvars.bat behavior
                save(self, "myenv.bat", "echo MYENV!!!\nset MYVC_CUSTOMVAR1=PATATA1")
                self.env_scripts.setdefault("build", []).append("myenv.bat")
                save(self, "myps.ps1", "echo MYPS1!!!!\n$env:MYVC_CUSTOMVAR2=\"PATATA2\"")
                self.env_scripts.setdefault("build", []).append("myps.ps1")
            def layout(self):
                self.folders.build = "mybuild"
                self.folders.generators = "mybuild"
            def test(self):
                self.run('mkdir "hello world"')
                self.run("dir")
                self.run('cd "hello world"')
                self.run("set MYVC_CUSTOMVAR1")
                self.run("set MYVC_CUSTOMVAR2")
            """)
    client.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                 "test_package/conanfile.py": test_package})
    client.run("create .")
    assert "hello world" in client.out
    assert "MYENV!!!" in client.out
    assert "MYPS1!!!!" in client.out
    assert "MYVC_CUSTOMVAR1=PATATA1" in client.out
    assert "MYVC_CUSTOMVAR2=PATATA2" in client.out
    # This was crashing because the .ps1 of test_package was not being cleaned
    client.run("create . -c tools.env.virtualenv:powershell=True")
    assert "hello world" in client.out
    assert "MYENV!!!" in client.out
    assert "MYPS1!!!!" in client.out
    assert "MYVC_CUSTOMVAR1=PATATA1" in client.out
    assert "MYVC_CUSTOMVAR2=PATATA2" in client.out

@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows powershell")
def test_vcvars():
    client = TestClient()
    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout, CMakeToolchain, CMakeDeps
        from conan.tools.env import VirtualBuildEnv

        class Conan(ConanFile):
           settings = "os", "compiler", "build_type", "arch"

           generators = 'CMakeDeps', 'CMakeToolchain'

           def layout(self):
              cmake_layout(self)

           def build(self):
              cmake = CMake(self)
              cmake.configure()
              cmake.build()
    """)
    hello_cpp = gen_function_cpp(name="main")
    cmakelists = gen_cmakelists(appname="hello", appsources=["hello.cpp"])
    client.save({"conanfile.py": conanfile, "hello.cpp": hello_cpp, "CMakeLists.txt": cmakelists})

    client.run("build . -c tools.env.virtualenv:powershell=True -c tools.cmake.cmaketoolchain:generator=Ninja")
    client.run_command(r'powershell.exe ".\build\Release\generators\conanbuild.ps1; dir env:"')
    #check the conanbuid.ps1 activation message
    assert "conanvcvars.ps1: Activated environment" in client.out
    #check that the new env variables are set
    assert "VSCMD_ARG_VCVARS_VER" in client.out

    client.run_command(r'powershell.exe ".\build\Release\generators\conanvcvars.ps1"')
    assert client.out.strip() == "conanvcvars.ps1: Activated environment"

    conanbuild = client.load(r".\build\Release\generators\conanbuild.ps1")
    vcvars_ps1 = client.load(r".\build\Release\generators\conanvcvars.ps1")
    #check that the conanvcvars.ps1 is being added to the conanbuild.ps1
    assert "conanvcvars.ps1" in conanbuild
    #check that the conanvcvars.ps1 is setting the environment
    assert "conanvcvars.bat&set" in vcvars_ps1
