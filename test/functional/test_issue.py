import json
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_issue():
    tc = TestClient()
    tc.run("new header_lib -d name=pkg4 -d version=1.0 -o=pkg4")
    tc.run("new header_lib -d name=pkg3 -d version=1.0 -o=pkg3_0 -d requires=pkg4/1.0")
    tc.run("new header_lib -d name=pkg3 -d version=1.1 -d requires=pkg4/1.0 -o=pkg3_1")
    # This pkg2 is necessary for the test to fail, removing it will make the test pass
    tc.run("new header_lib -d name=pkg2 -d version=1.0 -d requires=pkg3/[~1] -o=pkg2")
    tc.run("new cmake_lib -d name=pkg1 -d version=1.0 -d requires=pkg3/1.0 -d requires=pkg2/1.0 -o=pkg1")


    pkg1_conanfile = tc.load("pkg1/conanfile.py")
    pkg1_conanfile = pkg1_conanfile.replace('self.requires("pkg3/1.0")', 'self.requires("pkg3/1.0", visible=False)')

    pkg1_source = textwrap.dedent("""
    #include <iostream>
    #include "pkg4.h"


    void pkg1() {
        std::cout << "pkg1/1.0" << std::endl;
        pkg4();
    }

    void pkg1_print_vector(const std::vector<std::string> &strings) {
        for(std::vector<std::string>::const_iterator it = strings.begin(); it != strings.end(); ++it) {
            std::cout << "pkg1/1.0 " << *it << std::endl;
        }
    }
    """)

    tc.save({"pkg1/conanfile.py": pkg1_conanfile,
             "pkg1/src/pkg1.cpp": pkg1_source,
             "consumer/conanfile.py": GenConanfile("consumer").with_requires("pkg3/1.1", "pkg1/1.0")})

    tc.run("create pkg4")
    tc.run("create pkg3_0")
    tc.run("create pkg3_1")
    tc.run("create pkg2")
    tc.run("export pkg1")
    # This used to crash
    tc.run("install consumer --build=missing")
    assert "Install finished successfully" in tc.out
