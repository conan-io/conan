import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def bazelrc():
    return textwrap.dedent("""
        build:Debug -c dbg --copt=-g
        build:Release -c opt
        build:RelWithDebInfo -c opt --copt=-O3 --copt=-DNDEBUG
        build:MinSizeRel  -c opt --copt=-Os --copt=-DNDEBUG
        build --color=yes
        build:withTimeStamps --show_timestamps
        """)


@pytest.fixture(scope="module")
def base_profile():
    return textwrap.dedent("""
        include(default)
        [settings]
        build_type={build_type}

        [conf]
        # FIXME: Conan 2.x
        # tools.google.bazel:bazelrc_path=["{curdir}/mybazelrc"]
        # tools.google.bazel:configs=["{build_type}", "withTimeStamps"]
        tools.google.bazel:bazelrc_path={curdir}/mybazelrc
        tools.google.bazel:configs="{build_type}", "withTimeStamps"
        """)


@pytest.fixture(scope="function")
def client_exe(bazelrc):
    client = TestClient(path_with_spaces=False)
    # client.run("new bazel_exe -d name=myapp -d version=1.0")
    client.run("new myapp/1.0 -m bazel_exe")
    # The build:<config> define several configurations that can be activated by passing
    # the bazel config with tools.google.bazel:configs
    client.save({"mybazelrc": bazelrc})
    return client


@pytest.fixture(scope="function")
def client_lib(bazelrc):
    client = TestClient(path_with_spaces=False)
    # client.run("new bazel_lib -d name=mylib -d version=1.0")
    client.run("new mylib/1.0 -m bazel_lib")
    # The build:<config> define several configurations that can be activated by passing
    # the bazel config with tools.google.bazel:configs
    client.save({"mybazelrc": bazelrc})
    return client


@pytest.mark.skipif(platform.system() == "Linux", reason="Validate exception raises "
                                                         "only for Macos/Windows")
@pytest.mark.tool_bazel
def test_basic_exe():
    client = TestClient(path_with_spaces=False)
    # client.run("new bazel_lib -d name=mylib -d version=1.0")
    client.run("new mylib/1.0 -m bazel_lib")
    client.run("create . -o '*:shared=True'", assert_error=True)
    assert "Windows and Macos needs extra BUILD configuration" in client.out


@pytest.mark.parametrize("build_type", ["Debug", "Release", "RelWithDebInfo", "MinSizeRel"])
@pytest.mark.tool_bazel
def test_basic_exe(client_exe, build_type, base_profile):

    profile = base_profile.format(build_type=build_type, curdir=client_exe.current_folder)
    client_exe.save({"my_profile": profile})

    client_exe.run("create . --profile=./my_profile")
    if build_type != "Debug":
        assert "myapp/1.0: Hello World Release!" in client_exe.out
    else:
        assert "myapp/1.0: Hello World Debug!" in client_exe.out


@pytest.mark.parametrize("build_type", ["Debug", "Release", "RelWithDebInfo", "MinSizeRel"])
@pytest.mark.tool_bazel
def test_basic_lib(client_lib, build_type, base_profile):

    profile = base_profile.format(build_type=build_type, curdir=client_lib.current_folder)
    client_lib.save({"my_profile": profile})

    client_lib.run("create . --profile=./my_profile")
    if build_type != "Debug":
        assert "mylib/1.0: Hello World Release!" in client_lib.out
    else:
        assert "mylib/1.0: Hello World Debug!" in client_lib.out


@pytest.mark.tool_bazel
def test_transitive_consuming():

    client = TestClient(path_with_spaces=False)
    # A regular library made with CMake
    with client.chdir("myzip_lib"):
        # client.run("new cmake_lib -d name=myzip_lib -d version=1.2.11")
        client.run("new myzip_lib/1.2.11 -m cmake_lib")
        conanfile = client.load("conanfile.py")
        conanfile += """
        self.cpp_info.defines.append("MY_DEFINE=\\"MY_VALUE\\"")
        self.cpp_info.defines.append("MY_OTHER_DEFINE=2")
        if self.settings.os != "Windows":
            self.cpp_info.system_libs.append("m")
        else:
            self.cpp_info.system_libs.append("ws2_32")
        """
        client.save({"conanfile.py": conanfile})
        client.run("create .")

    # We prepare a consumer with Bazel (library myssl_lib using myzip_lib) and a test_package with an
    # example executable
    conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.google import Bazel, bazel_layout
            from conan.tools.files import copy


            class OpenSSLConan(ConanFile):
                name = "myssl_lib"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "main/*", "WORKSPACE"
                requires = "myzip_lib/1.2.11"

                generators = "BazelToolchain", "BazelDeps"

                def layout(self):
                    bazel_layout(self)

                def build(self):
                    bazel = Bazel(self)
                    bazel.build(target="//main:myssl_lib")

                def package(self):
                    dest_bin = os.path.join(self.package_folder, "bin")
                    dest_lib = os.path.join(self.package_folder, "lib")
                    build = os.path.join(self.build_folder, "bazel-bin", "main")
                    copy(self, "*.so", build, dest_bin, keep_path=False)
                    copy(self, "*.dll", build, dest_bin, keep_path=False)
                    copy(self, "*.dylib", build, dest_bin, keep_path=False)
                    copy(self, "*.a", build, dest_lib, keep_path=False)
                    copy(self, "*.lib", build, dest_lib, keep_path=False)
                    copy(self, "*myssl_lib.h", self.source_folder,
                         os.path.join(self.package_folder, "include"), keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["myssl_lib"]
                """)
    bazel_build = textwrap.dedent("""
            load("@rules_cc//cc:defs.bzl", "cc_library")

            cc_library(
                name = "myssl_lib",
                srcs = ["myssl_lib.cpp"],
                hdrs = ["myssl_lib.h"],
                deps = [
                    "@myzip_lib//:myzip_lib",
                ],
            )
            """)
    myssl_lib_c = textwrap.dedent("""
            #include <iostream>
            #include "myssl_lib.h"
            #include "myzip_lib.h"
            #include <math.h>

            void myssl_lib(){
                std::cout << "Calling OpenSSL function with define " << MY_DEFINE << " and other define " << MY_OTHER_DEFINE << "\\n";
                myzip_lib();
                // This comes from the systemlibs declared in the myzip_lib
                sqrt(25);
            }
            """)
    myssl_lib_c_win = textwrap.dedent("""
                #include <iostream>
                #include "myssl_lib.h"
                #include "myzip_lib.h"
                #include <WinSock2.h>

                void myssl_lib(){
                    SOCKET foo; // From the system library
                    std::cout << "Calling OpenSSL function with define " << MY_DEFINE << " and other define " << MY_OTHER_DEFINE << "\\n";
                    myzip_lib();
                }
                """)
    myssl_lib_h = textwrap.dedent("""
            void myssl_lib();
            """)

    bazel_workspace = textwrap.dedent("""
        load("@//:dependencies.bzl", "load_conan_dependencies")
        load_conan_dependencies()
    """)

    test_example = """#include "myssl_lib.h"

    int main() {{
        myssl_lib();
    }}
    """

    test_conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.google import Bazel, bazel_layout
    from conan.tools.build import cross_building


    class OpenSSLTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "BazelToolchain", "BazelDeps", "VirtualBuildEnv", "VirtualRunEnv"
        apply_env = False

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            bazel = Bazel(self)
            bazel.build(target="//main:example")

        def layout(self):
            bazel_layout(self)

        def test(self):
            if not cross_building(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "main", "example")
                self.run(cmd, env="conanrun")
    """)

    test_bazel_build = textwrap.dedent("""
        load("@rules_cc//cc:defs.bzl", "cc_binary")

        cc_binary(
            name = "example",
            srcs = ["example.cpp"],
            deps = [
                "@myssl_lib//:myssl_lib",
            ],
        )
        """)

    client.save({"conanfile.py": conanfile,
                 "main/BUILD": bazel_build,
                 "main/myssl_lib.cpp": myssl_lib_c if platform.system() != "Windows" else myssl_lib_c_win,
                 "main/myssl_lib.h": myssl_lib_h,
                 "WORKSPACE": bazel_workspace,
                 "test_package/conanfile.py": test_conanfile,
                 "test_package/main/example.cpp": test_example,
                 "test_package/main/BUILD": test_bazel_build,
                 "test_package/WORKSPACE": bazel_workspace
                 })

    client.run("create .")
    assert "Calling OpenSSL function with define MY_VALUE and other define 2" in client.out
    assert "myzip_lib/1.2.11: Hello World Release!"
