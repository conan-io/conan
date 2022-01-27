import os.path
import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app, pkg_cmake_test
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient


def test_shared_cmake_toolchain():
    client = TestClient(default_server_user=True)

    client.save(pkg_cmake("hello", "0.1"))
    client.run("create . -o hello:shared=True")
    client.save(pkg_cmake("chat", "0.1", requires=["hello/0.1"]), clean_first=True)
    client.run("create . -o chat:shared=True -o hello:shared=True")
    client.save(pkg_cmake_app("app", "0.1", requires=["chat/0.1"]), clean_first=True)
    client.run("create . -o chat:shared=True -o hello:shared=True")
    client.run("upload * -c -r default")
    client.run("remove * -f")

    client = TestClient(servers=client.servers)
    client.run("install --reference=app/0.1@ -o chat:shared=True -o hello:shared=True -g VirtualRunEnv")
    # This only finds "app" executable because the "app/0.1" is declaring package_type="application"
    # otherwise, run=None and nothing can tell us if the conanrunenv should have the PATH.
    command = environment_wrap_command("conanrun", "app", cwd=client.current_folder)

    client.run_command(command)
    assert "main: Release!" in client.out
    assert "chat: Release!" in client.out
    assert "hello: Release!" in client.out


def test_shared_cmake_toolchain_test_package():
    client = TestClient()
    files = pkg_cmake("hello", "0.1")
    files.update(pkg_cmake_test("hello"))
    client.save(files)
    client.run("create . -o hello:shared=True")
    assert "hello: Release!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_shared_same_dir_without_virtualenv_cmake_toolchain_test_package():
    client = TestClient()
    files = pkg_cmake("hello", "0.1")
    files.update(pkg_cmake_test("hello"))
    test_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conan.tools.cmake import CMake, cmake_layout

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

                def imports(self):
                    self.copy("*.dll", dst=self.folders.build, src="bin")
                    self.copy("*.dylib", dst=self.folders.build, src="lib")

                def test(self):
                    cmd = os.path.join(self.cpp.build.bindirs[0], "test")
                    # This is working without runenv because CMake is puting an internal rpath
                    # to the executable pointing to the dylib of hello, internally is doing something
                    # like: install_name_tool -add_rpath /path/to/hello/lib/libhello.dylib test
                    self.run(cmd)
            """)
    files["test_package/conanfile.py"] = test_conanfile

    client.save(files)
    client.run("create . -o hello:shared=True")
    assert "hello: Release!" in client.out

    # We can run the exe from the test package directory also, without environment
    exe_folder = os.path.join("test_package", "cmake-build-release")
    assert os.path.exists(os.path.join(client.current_folder, exe_folder, "test"))
    client.run_command(os.path.join(exe_folder, "test"))

    # We try to remove the hello package and run again the executable from the test package,
    # this time it should fail
    client.run("remove '*' -f")
    client.run_command(os.path.join(exe_folder, "test"), assert_error=True)

    # We set DYLD_LIBRARY_PATH=@executable_path, now it works again, because it has the shared
    # imported into the exe folder
    client.run_command("DYLD_LIBRARY_PATH=@executable_path "
                       "{}".format(os.path.join(exe_folder, "test")))

    # Alternative 2, set the rpath in cmake
    # PENDING, only viable when installing



