import os
import textwrap
import platform
import pytest

from conan.tools.cmake import CMakeToolchain
from conan.tools.cmake.presets import load_cmake_presets
from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_h, gen_function_cpp
from test.functional.utils import check_vs_runtime, check_exe_run
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain

        class Library(ConanFile):
            name = "hello"
            version = "1.0"
            settings = 'os', 'arch', 'compiler', 'build_type'
            exports_sources = 'hello.h', '*.cpp', 'CMakeLists.txt'
            options = {'shared': [True, False]}
            default_options = {'shared': False}

            def generate(self):
                tc = CMakeToolchain(self, generator="Ninja")
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.sep.join([".", "myapp"]))

            def package(self):
                cmake = CMake(self)
                cmake.install()
        """)

    test_client = TestClient(path_with_spaces=False)
    test_client.save({'conanfile.py': conanfile,
                      "CMakeLists.txt": gen_cmakelists(libsources=["hello.cpp"],
                                                       appsources=["main.cpp"],
                                                       install=True),
                      "hello.h": gen_function_h(name="hello"),
                      "hello.cpp": gen_function_cpp(name="hello", includes=["hello"]),
                      "main.cpp": gen_function_cpp(name="main", includes=["hello"],
                                                   calls=["hello"])})
    return test_client


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool("ninja")
def test_locally_build_linux(build_type, shared, client):
    settings = "-s os=Linux -s arch=x86_64 -s build_type={} -o hello/*:shared={}".format(build_type,
                                                                                       shared)
    client.run("install . {}".format(settings))
    client.run_command('cmake . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE={} -DCMAKE_BUILD_TYPE={}'
                       .format(CMakeToolchain.filename, build_type))

    client.run_command('ninja')
    if shared:
        assert "Linking CXX shared library libmylibrary.so" in client.out
    else:
        assert "Linking CXX static library libmylibrary.a" in client.out

    client.run_command("./myapp")
    check_exe_run(client.out, ["main", "hello"], "gcc", None, build_type, "x86_64", cppstd=None)

    # create should also work
    client.run("create . --name=hello --version=1.0 {}".format(settings))
    assert 'cmake -G "Ninja"' in client.out
    assert "main: {}!".format(build_type) in client.out
    client.run(f"install --requires=hello/1.0@ --deployer=full_deploy -of=mydeploy {settings}")
    deploy_path = os.path.join(client.current_folder, "mydeploy", "full_deploy", "host", "hello", "1.0",
                               build_type, "x86_64")
    client.run_command(f"LD_LIBRARY_PATH='{deploy_path}/lib' {deploy_path}/bin/myapp")
    check_exe_run(client.out, ["main", "hello"], "gcc", None, build_type, "x86_64", cppstd=None)


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool("ninja")
def test_locally_build_msvc(build_type, shared, client):
    msvc_version = "15"
    settings = "-s build_type={} -o hello/*:shared={}".format(build_type, shared)
    client.run("install . {}".format(settings))

    client.run_command('conanvcvars.bat && cmake . -G "Ninja" '
                       '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                       '-DCMAKE_BUILD_TYPE={}'.format(build_type))

    client.run_command("conanvcvars.bat && ninja")

    libname = "mylibrary.dll" if shared else "mylibrary.lib"
    assert libname in client.out

    client.run_command("myapp.exe")
    # TODO: Need full msvc version check
    check_exe_run(client.out, ["main", "hello"], "msvc", "19", build_type, "x86_64", cppstd="14")
    check_vs_runtime("myapp.exe", client, msvc_version, build_type, architecture="amd64")
    check_vs_runtime(libname, client, msvc_version, build_type, architecture="amd64")

    # create should also work
    client.run("create . --name=hello --version=1.0 {}".format(settings))
    assert 'cmake -G "Ninja"' in client.out
    assert "main: {}!".format(build_type) in client.out
    client.run(f"install --requires=hello/1.0@ --deployer=full_deploy -of=mydeploy {settings}")
    client.run_command(fr"mydeploy\full_deploy\host\hello\1.0\{build_type}\x86_64\bin\myapp.exe")
    check_exe_run(client.out, ["main", "hello"], "msvc", "19", build_type, "x86_64", cppstd="14")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.tool("ninja")
def test_locally_build_msvc_toolset(client):
    msvc_version = "15"
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=msvc
        compiler.version=190
        compiler.runtime=dynamic
        compiler.cppstd=14
        build_type=Release
        arch=x86_64
        [conf]
        tools.cmake.cmaketoolchain:generator=Ninja
        tools.microsoft.msbuild:vs_version = 15
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile")

    client.run_command('conanvcvars.bat && cmake . -G "Ninja" '
                       '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                       '-DCMAKE_BUILD_TYPE=Release')

    client.run_command("conanvcvars.bat && ninja")

    client.run_command("myapp.exe")

    # Checking that compiler is indeed version 19.0, not 19.1-default of VS15
    check_exe_run(client.out, ["main", "hello"], "msvc", "190", "Release", "x86_64", cppstd="14")
    check_vs_runtime("myapp.exe", client, msvc_version, "Release", architecture="amd64")
    check_vs_runtime("mylibrary.lib", client, msvc_version, "Release", architecture="amd64")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool("mingw64")
@pytest.mark.tool("ninja")
def test_locally_build_gcc(build_type, shared, client):
    # FIXME: Note the gcc version is still incorrect
    gcc = ("-s os=Windows -s compiler=gcc -s compiler.version=4.9 -s compiler.libcxx=libstdc++ "
           "-s arch=x86_64 -s build_type={}".format(build_type))

    client.run("install . {} -o hello/*:shared={}".format(gcc, shared))

    client.run_command('cmake . -G "Ninja" '
                       '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                       '-DCMAKE_BUILD_TYPE={}'.format(build_type))

    libname = "mylibrary.dll" if shared else "libmylibrary.a"
    client.run_command("ninja")
    assert libname in client.out

    client.run_command("myapp.exe")
    # TODO: Need full gcc version check
    check_exe_run(client.out, ["main", "hello"], "gcc", None, build_type, "x86_64", cppstd=None,
                  subsystem="mingw64")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires apple-clang")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool("ninja")
def test_locally_build_macos(build_type, shared, client):
    client.run('install . -s os=Macos -s arch=x86_64 -s build_type={} -o hello/*:shared={}'
               .format(build_type, shared))
    client.run_command('cmake . -G"Ninja" -DCMAKE_TOOLCHAIN_FILE={} -DCMAKE_BUILD_TYPE={}'
                       .format(CMakeToolchain.filename, build_type))

    client.run_command('ninja')
    if shared:
        assert "Linking CXX shared library libmylibrary.dylib" in client.out
    else:
        assert "Linking CXX static library libmylibrary.a" in client.out

    command_str = 'DYLD_LIBRARY_PATH="%s" ./myapp' % client.current_folder
    client.run_command(command_str)
    check_exe_run(client.out, ["main", "hello"], "apple-clang", None, build_type, "x86_64",
                  cppstd=None)


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.tool("visual_studio")
def test_ninja_conf():
    conanfile = GenConanfile().with_generator("CMakeToolchain").with_settings("os", "compiler",
                                                                              "build_type", "arch")
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
        compiler.cppstd=14
        build_type=Release
        arch=x86_64
        [conf]
        tools.cmake.cmaketoolchain:generator=Ninja
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "profile": profile})
    client.run("install . -pr=profile")
    presets = load_cmake_presets(client.current_folder)
    generator = presets["configurePresets"][0]["generator"]

    assert generator == "Ninja"
    vcvars = client.load("conanvcvars.bat")
    assert "2017" in vcvars

    # toolchain cannot define the CMAKE_GENERATOR_TOOLSET for Ninja
    cmake = client.load("conan_toolchain.cmake")
    assert "CMAKE_GENERATOR_TOOLSET" not in cmake
