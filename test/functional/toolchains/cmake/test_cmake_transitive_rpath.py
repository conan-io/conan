from platform import platform
import textwrap
import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient

@pytest.mark.skipif(platform.system() != "Linux", reason="Linux/gcc required for -rpath/-rpath-link testing")
@pytest.mark.parametrize("use_cmake_config_deps", [True, False])
def test_cmake_transitive_rpath(use_cmake_config_deps):
    c = TestClient()

     
    extra_profile = textwrap.dedent("""
        [conf]
        tools.build:sysroot=/path/to/nowhere
    """)

    # Avoid using any C or C++ standard functionality, so that we can "redirect" the sysroot
    # to an empty or non-existing directory
    foo_h = textwrap.dedent("""
        #pragma once
        int foo(int x, int y);
    """)
    foo_cpp = textwrap.dedent("""
        #include "foo.h"
        int foo(int x, int y) {
            return x + y;
        }
    """)
    foo_test = textwrap.dedent("""
        #include "foo.h"
        int main() { return foo(2, 3) == 5 ? 0 : 1; }
    """)
    bar_h = textwrap.dedent("""
        #pragma once
        int bar(int x, int y);
    """)
    bar_cpp = textwrap.dedent("""
        #include "bar.h"
        #include "foo.h"
        int bar(int x, int y) {
            return foo(x, y) * 2;
        }
    """)
    bar_test = textwrap.dedent("""
        #include "bar.h"
        int main() { return bar(2, 3) == 10 ? 0 : 1; }
    """)

    c.save({"extra_profile": extra_profile})
    extra_conf = "-c tools.cmake.cmakedeps:new=will_break_next" if use_cmake_config_deps else ""
    with c.chdir("foo"):
        c.run("new cmake_lib -d name=foo -d version=0.1")
        c.save({"include/foo.h": foo_h,
                "src/foo.cpp": foo_cpp,
                "test_package/src/example.cpp": foo_test})
        c.run(f"create . -o '*:shared=True' -pr=default -pr=../extra_profile {extra_conf}")

    with c.chdir("bar"):
        c.run("new cmake_lib -d name=bar -d version=0.1 -d requires=foo/0.1")
        c.save({"include/bar.h": bar_h,
                "src/bar.cpp": bar_cpp,
                "test_package/src/example.cpp": bar_test})
        c.run(f"create . -o '*:shared=True' -pr=default -pr=../extra_profile {extra_conf}")
    with c.chdir("app"):
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=bar/0.1")
        c.save({"src/main.cpp": bar_test,
                "src/app.cpp": ""})
        c.run(f"create . -o '*:shared=True' -pr=default -pr=../extra_profile {extra_conf}")