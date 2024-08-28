import platform
import textwrap

import pytest

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def bazel_output_root_dir():
    return temp_folder(path_with_spaces=False).replace("\\", "/")


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
        tools.google.bazel:bazelrc_path=["{curdir}/mybazelrc"]
        tools.google.bazel:configs=["{build_type}", "withTimeStamps"]
        """)


@pytest.mark.parametrize("build_type", ["Debug", "Release", "RelWithDebInfo", "MinSizeRel"])
@pytest.mark.tool("bazel", "6.3.2")
def test_basic_exe_6x(bazelrc, build_type, base_profile, bazel_output_root_dir):
    client = TestClient(path_with_spaces=False)
    client.run(f"new bazel_exe -d name=myapp -d version=1.0 -d output_root_dir={bazel_output_root_dir}")
    # The build:<config> define several configurations that can be activated by passing
    # the bazel config with tools.google.bazel:configs
    client.save({"mybazelrc": bazelrc})
    profile = base_profile.format(build_type=build_type,
                                  curdir=client.current_folder.replace("\\", "/"))
    client.save({"my_profile": profile})
    client.run("create . --profile=./my_profile")
    if build_type != "Debug":
        assert "myapp/1.0: Hello World Release!" in client.out
    else:
        assert "myapp/1.0: Hello World Debug!" in client.out


@pytest.mark.parametrize("build_type", ["Debug", "Release", "RelWithDebInfo", "MinSizeRel"])
@pytest.mark.tool("bazel", "7.1.2")
def test_basic_exe(bazelrc, build_type, base_profile, bazel_output_root_dir):
    client = TestClient(path_with_spaces=False)
    client.run(f"new bazel_7_exe -d name=myapp -d version=1.0 -d output_root_dir={bazel_output_root_dir}")
    # The build:<config> define several configurations that can be activated by passing
    # the bazel config with tools.google.bazel:configs
    client.save({"mybazelrc": bazelrc})
    profile = base_profile.format(build_type=build_type,
                                  curdir=client.current_folder.replace("\\", "/"))
    client.save({"my_profile": profile})
    client.run("create . --profile=./my_profile")
    if build_type != "Debug":
        assert "myapp/1.0: Hello World Release!" in client.out
    else:
        assert "myapp/1.0: Hello World Debug!" in client.out


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.tool("bazel", "6.3.2")
def test_transitive_libs_consuming_6x(shared, bazel_output_root_dir):
    """
    Testing the next dependencies structure for shared/static libs

    /.
    |- myfirstlib/
         |- conanfile.py
         |- WORKSPACE
         |- main/
            |- BUILD
            |- myfirstlib.cpp
            |- myfirstlib.h
    |- mysecondlib/  (requires myfirstlib)
         |- conanfile.py
         |- WORKSPACE
         |- main/
            |- BUILD
            |- mysecondlib.cpp
            |- mysecondlib.h
         |- test_package/
            |- WORKSPACE
            |- conanfile.py
            |- main
                |- example.cpp
                |- BUILD
    """
    client = TestClient(path_with_spaces=False)
    # A regular library made with Bazel
    with client.chdir("myfirstlib"):
        client.run(f"new bazel_lib -d name=myfirstlib -d version=1.2.11 -d output_root_dir={bazel_output_root_dir}")
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
        client.run(f"create . -o '*:shared={shared}' -tf ''")  # skipping tests

    with client.chdir("mysecondlib"):
        # We prepare a consumer with Bazel (library mysecondlib using myfirstlib)
        # and a test_package with an example executable
        os_ = platform.system()
        client.run(f"new bazel_lib -d name=mysecondlib -d version=1.0 -d output_root_dir={bazel_output_root_dir}")
        conanfile = client.load("conanfile.py")
        conanfile = conanfile.replace('generators = "BazelToolchain"',
                                      'generators = "BazelToolchain", "BazelDeps"\n'
                                      '    requires = "myfirstlib/1.2.11"')
        workspace = textwrap.dedent("""
        load("@//conan:dependencies.bzl", "load_conan_dependencies")
        load_conan_dependencies()
        """)
        bazel_build_linux = textwrap.dedent("""\
        cc_library(
            name = "mysecondlib",
            srcs = ["mysecondlib.cpp"],
            hdrs = ["mysecondlib.h"],
            deps = [ "@myfirstlib//:myfirstlib" ]
        )
        """)
        bazel_build = textwrap.dedent("""\
        cc_library(
            name = "mysecondlib",
            srcs = ["mysecondlib.cpp"],
            hdrs = ["mysecondlib.h"],
            deps = [ "@myfirstlib//:myfirstlib" ]
        )

        cc_shared_library(
            name = "mysecondlib_shared",
            shared_lib_name = "libmysecondlib_shared.{}",
            deps = [":mysecondlib"],
        )
        """.format("dylib" if os_ == "Darwin" else "dll"))
        mysecondlib_cpp = textwrap.dedent("""
        #include <iostream>
        #include "mysecondlib.h"
        #include "myfirstlib.h"
        #include <cmath>

        void mysecondlib(){
            std::cout << "mysecondlib() First define " << MY_DEFINE << " and other define " << MY_OTHER_DEFINE << std::endl;
            myfirstlib();
            // This comes from the systemlibs declared in the myfirstlib
            sqrt(25);
        }
        void mysecondlib_print_vector(const std::vector<std::string> &strings) {
            for(std::vector<std::string>::const_iterator it = strings.begin(); it != strings.end(); ++it) {
                std::cout << "mysecondlib/1.0 " << *it << std::endl;
            }
        }
        """)
        mysecondlib_cpp_win = textwrap.dedent("""
        #include <iostream>
        #include "mysecondlib.h"
        #include "myfirstlib.h"
        #include <WinSock2.h>

        void mysecondlib(){
            SOCKET foo; // From the system library
            std::cout << "mysecondlib() First define " << MY_DEFINE << " and other define " << MY_OTHER_DEFINE << std::endl;
            myfirstlib();
        }
        void mysecondlib_print_vector(const std::vector<std::string> &strings) {
            for(std::vector<std::string>::const_iterator it = strings.begin(); it != strings.end(); ++it) {
                std::cout << "mysecondlib/1.0 " << *it << std::endl;
            }
        }
        """)
        # Overwriting files
        client.save({"conanfile.py": conanfile,
                     "WORKSPACE": workspace,
                     "main/BUILD": bazel_build_linux if os_ == "Linux" else bazel_build,
                     "main/mysecondlib.cpp": mysecondlib_cpp if os_ != "Windows" else mysecondlib_cpp_win,
                     })

        client.run(f"create . -o '*:shared={shared}'")
        assert "mysecondlib() First define MY_VALUE and other define 2" in client.out
        assert "myfirstlib/1.2.11: Hello World Release!"


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.tool("bazel", "7.1.2")
@pytest.mark.skip(reason="Conan CI is failing because of this (likely related to parallel"
                         "tests running. Skipping it for now!")
def test_transitive_libs_consuming(shared, bazel_output_root_dir):
    """
    Testing the next dependencies structure for shared/static libs

    /.
    |- myfirstlib/
         |- conanfile.py
         |- MODULE.bazel
         |- main/
            |- BUILD
            |- myfirstlib.cpp
            |- myfirstlib.h
    |- mysecondlib/  (requires myfirstlib)
         |- conanfile.py
         |- MODULE.bazel
         |- main/
            |- BUILD
            |- mysecondlib.cpp
            |- mysecondlib.h
         |- test_package/
            |- MODULE.bazel
            |- conanfile.py
            |- main
                |- example.cpp
                |- BUILD
    """
    client = TestClient(path_with_spaces=False)
    # A regular library made with Bazel
    with client.chdir("myfirstlib"):
        client.run(f"new bazel_7_lib -d name=myfirstlib -d version=1.2.11 -d output_root_dir={bazel_output_root_dir}")
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
        client.run(f"create . -o '*:shared={shared}' -tf ''")  # skipping tests

    with client.chdir("mysecondlib"):
        # We prepare a consumer with Bazel (library mysecondlib using myfirstlib)
        # and a test_package with an example executable
        os_ = platform.system()
        client.run(f"new bazel_7_lib -d name=mysecondlib -d version=1.0 -d output_root_dir={bazel_output_root_dir}")
        conanfile = client.load("conanfile.py")
        conanfile = conanfile.replace('generators = "BazelToolchain"',
                                      'generators = "BazelToolchain", "BazelDeps"\n'
                                      '    requires = "myfirstlib/1.2.11"')
        workspace = textwrap.dedent("""
        load_conan_dependencies = use_extension("//conan:conan_deps_module_extension.bzl", "conan_extension")
        use_repo(load_conan_dependencies, "myfirstlib")
        """)
        bazel_build_linux = textwrap.dedent("""\
        cc_library(
            name = "mysecondlib",
            srcs = ["mysecondlib.cpp"],
            hdrs = ["mysecondlib.h"],
            deps = [ "@myfirstlib//:myfirstlib" ]
        )
        """)
        bazel_build = textwrap.dedent("""\
        cc_library(
            name = "mysecondlib",
            srcs = ["mysecondlib.cpp"],
            hdrs = ["mysecondlib.h"],
            deps = [ "@myfirstlib//:myfirstlib" ]
        )

        cc_shared_library(
            name = "mysecondlib_shared",
            shared_lib_name = "libmysecondlib_shared.{}",
            deps = [":mysecondlib"],
        )
        """.format("dylib" if os_ == "Darwin" else "dll"))
        mysecondlib_cpp = textwrap.dedent("""
        #include <iostream>
        #include "mysecondlib.h"
        #include "myfirstlib.h"
        #include <cmath>

        void mysecondlib(){
            std::cout << "mysecondlib() First define " << MY_DEFINE << " and other define " << MY_OTHER_DEFINE << std::endl;
            myfirstlib();
            // This comes from the systemlibs declared in the myfirstlib
            sqrt(25);
        }
        void mysecondlib_print_vector(const std::vector<std::string> &strings) {
            for(std::vector<std::string>::const_iterator it = strings.begin(); it != strings.end(); ++it) {
                std::cout << "mysecondlib/1.0 " << *it << std::endl;
            }
        }
        """)
        mysecondlib_cpp_win = textwrap.dedent("""
        #include <iostream>
        #include "mysecondlib.h"
        #include "myfirstlib.h"
        #include <WinSock2.h>

        void mysecondlib(){
            SOCKET foo; // From the system library
            std::cout << "mysecondlib() First define " << MY_DEFINE << " and other define " << MY_OTHER_DEFINE << std::endl;
            myfirstlib();
        }
        void mysecondlib_print_vector(const std::vector<std::string> &strings) {
            for(std::vector<std::string>::const_iterator it = strings.begin(); it != strings.end(); ++it) {
                std::cout << "mysecondlib/1.0 " << *it << std::endl;
            }
        }
        """)
        # Overwriting files
        client.save({"conanfile.py": conanfile,
                     "MODULE.bazel": workspace,
                     "main/BUILD": bazel_build_linux if os_ == "Linux" else bazel_build,
                     "main/mysecondlib.cpp": mysecondlib_cpp if os_ != "Windows" else mysecondlib_cpp_win,
                     })

        client.run(f"create . -o '*:shared={shared}'")
        assert "mysecondlib() First define MY_VALUE and other define 2" in client.out
        assert "myfirstlib/1.2.11: Hello World Release!"
