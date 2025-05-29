import os.path
import platform
import textwrap

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.tools import TestClient
from conan.internal.util.files import rmdir


@pytest.fixture(scope="module")
def transitive_shared_client():
    # TODO: Reuse fixtures
    client = TestClient(default_server_user=True)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create . -o hello/*:shared=True -tf=")
    client.save({}, clean_first=True)
    client.run("new cmake_lib -d name=chat -d version=0.1 -d requires=hello/0.1")
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True -tf=")

    client.save({}, clean_first=True)
    client.run("new cmake_exe -d name=app -d version=0.1 -d requires=chat/0.1")
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True -tf=")
    client.run("upload * -c -r default")
    client.run("remove * -c")
    return client


@pytest.mark.tool("cmake")
def test_other_client_can_execute(transitive_shared_client):
    _check_install_run(transitive_shared_client)


def _check_install_run(client):
    client = TestClient(servers=client.servers)
    client.run("install --requires=app/0.1@ -o chat*:shared=True -o hello/*:shared=True "
               "-g VirtualRunEnv")
    # This only finds "app" executable because the "app/0.1" is declaring package_type="application"
    # otherwise, run=None and nothing can tell us if the conanrunenv should have the PATH.
    command = environment_wrap_command(ConanFileMock(), "conanrun", client.current_folder, "app")

    client.run_command(command)
    assert "app/0.1: Hello World Release!" in client.out
    assert "chat/0.1: Hello World Release!" in client.out
    assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.tool("cmake")
def test_other_client_can_link_cmake(transitive_shared_client):
    client = transitive_shared_client
    # https://github.com/conan-io/conan/issues/13000
    # This failed, because of rpath link in Linux
    client = TestClient(servers=client.servers, inputs=["admin", "password"])
    client.run("new cmake_exe -d name=app -d version=0.1 -d requires=chat/0.1")
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True -tf=")

    # check exe also keep running
    client.run("upload * -c -r default")
    client.run("remove * -c")
    _check_install_run(transitive_shared_client)


# FIXME: Move to the correct Meson space
@pytest.mark.tool("meson")
@pytest.mark.tool("pkg_config")
def test_other_client_can_link_meson(transitive_shared_client):
    client = transitive_shared_client
    # https://github.com/conan-io/conan/issues/13000
    # This failed, because of rpath link in Linux
    client = TestClient(servers=client.servers, inputs=["admin", "password"], path_with_spaces=False)
    client.run("new meson_exe -d name=app -d version=0.1 -d requires=chat/0.1")
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True")
    # TODO Check that static builds too
    # client.run("create . --build=missing")


# FIXME: Move to the correct Meson space
@pytest.mark.tool("autotools")
@pytest.mark.skipif(platform.system() == "Windows", reason="Autotools needed")
def test_other_client_can_link_autotools(transitive_shared_client):
    client = transitive_shared_client
    # https://github.com/conan-io/conan/issues/13000
    # This failed, because of rpath link in Linux
    client = TestClient(servers=client.servers, inputs=["admin", "password"], path_with_spaces=False)
    client.run("new autotools_exe -d name=app -d version=0.1 -d requires=chat/0.1")
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True")
    # TODO Check that static builds too
    # client.run("create . --build=missing")


@pytest.mark.tool("cmake")
def test_shared_cmake_toolchain_components():
    """ the same as above, but with components.
    """
    client = TestClient(default_server_user=True)

    client.run("new cmake_lib -d name=hello -d version=0.1")
    conanfile = client.load("conanfile.py")
    conanfile2 = conanfile.replace('self.cpp_info.libs = ["hello"]',
                                   'self.cpp_info.components["hi"].libs = ["hello"]')
    assert conanfile != conanfile2
    client.save({"conanfile.py": conanfile2})
    client.run("create . -o hello/*:shared=True -tf=")
    # Chat
    client.save({}, clean_first=True)
    client.run("new cmake_lib -d name=chat -d version=0.1 -d requires=hello/0.1")
    conanfile = client.load("conanfile.py")
    conanfile2 = conanfile.replace('self.cpp_info.libs = ["chat"]',
                                   'self.cpp_info.components["talk"].libs = ["chat"]\n'
                                   '        self.cpp_info.components["talk"].requires=["hello::hi"]')
    assert conanfile != conanfile2
    client.save({"conanfile.py": conanfile2})
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True -tf=")

    # App
    client.save({}, clean_first=True)
    client.run("new cmake_exe -d name=app -d version=0.1 -d requires=chat/0.1")
    cmakelist = client.load("CMakeLists.txt")
    cmakelist2 = cmakelist.replace('target_link_libraries(app PRIVATE chat::chat)',
                                   'target_link_libraries(app PRIVATE chat::talk)')
    assert cmakelist != cmakelist2
    client.save({"CMakeLists.txt": cmakelist2})
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True -tf=")
    client.run("upload * -c -r default")
    client.run("remove * -c")

    client = TestClient(servers=client.servers)
    client.run("install --requires=app/0.1@ -o chat*:shared=True -o hello/*:shared=True")
    # This only finds "app" executable because the "app/0.1" is declaring package_type="application"
    # otherwise, run=None and nothing can tell us if the conanrunenv should have the PATH.
    command = environment_wrap_command(ConanFileMock(), "conanrun", client.current_folder, "app")

    client.run_command(command)
    assert "app/0.1 test_package" in client.out
    assert "app/0.1: Hello World Release!" in client.out
    assert "chat/0.1: Hello World Release!" in client.out
    assert "hello/0.1: Hello World Release!" in client.out

    # https://github.com/conan-io/conan/issues/13000
    # This failed, because of rpath link in Linux
    client = TestClient(servers=client.servers, inputs=["admin", "password"])
    client.run("new cmake_exe -d name=app -d version=0.1 -d requires=chat/0.1")
    client.run("create . -o chat/*:shared=True -o hello/*:shared=True")
    client.run("upload * -c -r default")
    client.run("remove * -c")

    client = TestClient(servers=client.servers)
    client.run("install --requires=app/0.1@ -o chat*:shared=True -o hello/*:shared=True")
    # This only finds "app" executable because the "app/0.1" is declaring package_type="application"
    # otherwise, run=None and nothing can tell us if the conanrunenv should have the PATH.
    command = environment_wrap_command(ConanFileMock(), "conanrun", client.current_folder, "app")

    client.run_command(command)
    assert "app/0.1: Hello World Release!" in client.out
    assert "chat/0.1: Hello World Release!" in client.out
    assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.tool("cmake")
def test_shared_cmake_toolchain_test_package():
    # TODO: This is already tested in other places
    client = TestClient()
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create . -o hello/*:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out
    assert "hello/0.1 test_package" in client.out


@pytest.fixture()
def test_client_shared():
    client = TestClient()
    client.run("new -d name=hello -d version=0.1 cmake_lib")
    test_conanfile = textwrap.dedent("""
                import os
                from conan import ConanFile
                from conan.tools.cmake import CMake, cmake_layout
                from conan.tools.files import copy

                class Pkg(ConanFile):
                    settings = "os", "compiler", "arch", "build_type"
                    generators = "CMakeToolchain", "CMakeDeps"

                    def requirements(self):
                        self.requires(self.tested_reference_str)

                    def layout(self):
                        cmake_layout(self)

                    def build(self):
                        cmake = CMake(self)
                        cmake.configure()
                        cmake.build()

                    def generate(self):
                        for dep in self.dependencies.values():
                            copy(self, "*.dylib", dep.cpp_info.libdirs[0], self.build_folder)
                            copy(self, "*.dll", dep.cpp_info.libdirs[0], self.build_folder)

                    def test(self):
                        cmd = os.path.join(self.cpp.build.bindirs[0], "example")
                        # This is working without runenv because CMake is puting an internal rpath
                        # to the executable pointing to the dylib of hello, internally is doing something
                        # like: install_name_tool -add_rpath /path/to/hello/lib/libhello.dylib test
                        self.run(cmd)
                """)
    files = {"test_package/conanfile.py": test_conanfile}

    client.save(files)
    client.run("create . -o hello*:shared=True")
    assert "Hello World Release!" in client.out

    # We can run the exe from the test package directory also, without environment
    # because there is an internal RPATH in the exe with an abs path to the "hello"
    build_folder = client.created_test_build_folder("hello/0.1")
    exe_folder = os.path.join("test_package", build_folder)
    client.test_exe_folder = exe_folder
    assert os.path.exists(os.path.join(client.current_folder, exe_folder, "example"))
    client.run_command(os.path.join(exe_folder, "example"))

    # We try to remove the hello package and run again the executable from the test package,
    # this time it should fail, it doesn't find the shared library
    client.run("remove '*' -c")
    client.run_command(os.path.join(exe_folder, "example"), assert_error=True)
    return client


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_shared_same_dir_using_tool(test_client_shared):
    """
    If we build an executable in Mac and we want it to locate the shared libraries in the same
    directory, we have different alternatives, here we use the "install_name_tool"
    """
    exe_folder = test_client_shared.test_exe_folder
    # Alternative 1, add the "." to the rpaths so the @rpath from the exe can be replaced with "."
    test_client_shared.current_folder = os.path.join(test_client_shared.current_folder, exe_folder)
    test_client_shared.run_command("install_name_tool -add_rpath '.' example")
    test_client_shared.run_command("./{}".format("example"))


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_shared_same_dir_using_cmake(test_client_shared):
    """
        If we build an executable in Mac and we want it to locate the shared libraries in the same
        directory, we have different alternatives, here we use CMake to adjust CMAKE_INSTALL_RPATH
        to @executable_path so the exe knows that can replace @rpath with the current dir
    """

    # Alternative 2, set the rpath in cmake
    # Only viable when installing with cmake
    cmake = """
    set(CMAKE_CXX_COMPILER_WORKS 1)
    set(CMAKE_CXX_ABI_COMPILED 1)
    set(CMAKE_C_COMPILER_WORKS 1)
    set(CMAKE_C_ABI_COMPILED 1)
    cmake_minimum_required(VERSION 3.15)
    project(project CXX)

    set(CMAKE_INSTALL_RPATH "@executable_path")

    find_package(hello)
    add_executable(test  src/example.cpp )
    target_link_libraries(test  hello::hello)
    # Hardcoded installation path to keep the exe in the same place in the tests
    install(TARGETS test DESTINATION "bin")
    """
    # Same test conanfile but calling cmake.install()
    cf = textwrap.dedent("""
                import os
                from conan import ConanFile
                from conan.tools.files import copy
                from conan.tools.cmake import CMake, cmake_layout

                class Pkg(ConanFile):
                    settings = "os", "compiler", "arch", "build_type"
                    generators = "CMakeToolchain", "CMakeDeps"

                    def generate(self):
                        # The exe is installed by cmake at test_package/bin
                        dest = os.path.join(self.recipe_folder, "bin")
                        for dep in self.dependencies.values():
                            copy(self, "*.dylib", dep.cpp_info.libdirs[0], dest)

                    def requirements(self):
                        self.requires(self.tested_reference_str)

                    def layout(self):
                        cmake_layout(self)

                    def build(self):
                        cmake = CMake(self)
                        cmake.configure()
                        cmake.build()
                        cmake.install()

                    def test(self):
                        cmd = os.path.join(self.cpp.build.bindirs[0], "test")
                        # This is working without runenv because CMake is puting an internal rpath
                        # to the executable pointing to the dylib of hello, internally is doing something
                        # like: install_name_tool -add_rpath /path/to/hello/lib/libhello.dylib test
                        self.run(cmd)
                """)
    test_client_shared.save({"test_package/CMakeLists.txt": cmake, "test_package/conanfile.py": cf})
    test_client_shared.run("create . -o hello*:shared=True")
    test_client_shared.run("remove '*' -c")
    exe_folder = os.path.join("test_package", "bin")
    test_client_shared.run_command(os.path.join(exe_folder, "test"))


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_shared_same_dir_using_env_var_current_dir(test_client_shared):
    """
        If we build an executable in Mac and we want it to locate the shared libraries in the same
        directory, we have different alternatives, here we set DYLD_LIBRARY_PATH before calling
        the executable but running in current dir
    """

    # Alternative 3, FAILING IN CI, set DYLD_LIBRARY_PATH in the current dir
    exe_folder = test_client_shared.test_exe_folder
    rmdir(os.path.join(test_client_shared.current_folder, exe_folder))
    test_client_shared.run("create . -o hello*:shared=True")
    test_client_shared.run("remove '*' -c")
    test_client_shared.current_folder = os.path.join(test_client_shared.current_folder, exe_folder)
    test_client_shared.run_command("DYLD_LIBRARY_PATH=$(pwd) ./example")
    test_client_shared.run_command("DYLD_LIBRARY_PATH=. ./example")
    # This assert is not working in CI, only locally
    # test_client_shared.run_command("DYLD_LIBRARY_PATH=@executable_path ./test")
