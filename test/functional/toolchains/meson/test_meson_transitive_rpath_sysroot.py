import platform
import textwrap

import pytest
from conan.test.utils.tools import TestClient


@pytest.mark.tool("ninja")
@pytest.mark.tool("meson")
@pytest.mark.tool("pkg_config")
@pytest.mark.skipif(platform.system() != "Linux", reason="Linux/gcc required for -rpath/-rpath-link testing")
def test_meson_sysroot_transitive_rpath():
    c = TestClient()

    extra_profile = textwrap.dedent("""
        [conf]
        tools.build:sysroot=/path/to/nowhere
        tools.build:add_rpath_link=True
    """)

    foobar_h = textwrap.dedent("""
        #pragma once
        int foobar(int x, int y);
    """)

    foobar_cpp = textwrap.dedent("""
        #include "foobar.h"
        int foobar(int x, int y) {
            return x + y;
        }
    """)

    test_package_cpp = textwrap.dedent("""
        #include "foobar.h"
        int main() { return foobar(2, 3) == 5 ? 0 : 1; }
    """)

    consumer_meson_build = textwrap.dedent("""
        project('consumer ', 'cpp')
        cxx = meson.get_compiler('cpp')
        #add_project_link_arguments('--sysroot=/path/to/nowhere', language: 'cpp')
        foobar = dependency('foobar', required: true)
        consumer_lib = library('consumer', 'src/consumer.cpp', install: true, dependencies: foobar)
        executable('consumer_app', 'src/main.cpp', install: true, link_with: consumer_lib)
    """)

    consumer_consumer_h = textwrap.dedent("""
        #pragma once
        int consumer(int x, int y);
    """)

    consumer_consumer_cpp = textwrap.dedent("""
        #include "consumer.h"
        #include "foobar.h"
        int consumer(int x, int y) {
            return foobar(x, y) * 2;
        }
    """)

    consumer_main_cpp = textwrap.dedent("""
        #include "consumer.h"
        int main() { return consumer(2, 3) == 10 ? 0 : 1; }
    """)

    c.save({"extra_profile": extra_profile})
    with c.chdir("foobar"):
        c.run("new cmake_lib -d name=foobar -d version=1.0")
        c.save({"include/foobar.h": foobar_h,
                "src/foobar.cpp": foobar_cpp,
                "test_package/src/example.cpp": test_package_cpp,})
        
        c.run(f'create . -o "*:shared=True" -pr=default -pr=../extra_profile')

    with c.chdir("consumer"):
        c.run(f'new meson_lib -d name=consumer -d version=1.0 -d requires=foobar/1.0')
        c.save({"src/consumer.cpp": consumer_consumer_cpp,
                "src/main.cpp": consumer_main_cpp,
                "src/consumer.h": consumer_consumer_h,
                "meson.build": consumer_meson_build})
        c.run(f'create . -o "*:shared=True" -tf= -pr=default -pr=../extra_profile')
