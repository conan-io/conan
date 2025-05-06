from conan.test.utils.tools import TestClient


def test_issue():
    tc = TestClient()
    tc.run("new header_lib -d name=pkg4 -d version=1.0 -o=pkg4")
    tc.run("new header_lib -d name=pkg3 -d version=1.1 -d requires=pkg4/1.0 -o=pkg3_1")
    tc.run("new header_lib -d name=pkg3 -d version=1.0 -d requires=pkg4/1.0 -o=pkg3_0")
    tc.run("new cmake_lib -d name=pkg2 -d version=1.0 -d requires=pkg3/1.0 -o=pkg2")
    tc.run("new cmake_lib -d name=pkg1 -d version=1.0 -d requires=pkg2/1.0 -d requires=pkg3/1.1 -o=pkg1")

    pkg2_conanfile = tc.load("pkg2/conanfile.py")
    pkg2_conanfile = pkg2_conanfile.replace('self.requires("pkg3/1.0")', 'self.requires("pkg3/1.0", visible=False)')

    pkg2_source_cpp = tc.load("pkg2/src/pkg2.cpp")
    pkg2_source_cpp = pkg2_source_cpp.replace('#include "pkg3.h"', '#include "pkg3.h"\n#include "pkg4.h"')
    pkg2_source_cpp = pkg2_source_cpp.replace('pkg3();', 'pkg3();\npkg4();')

    tc.save({"pkg2/conanfile.py": pkg2_conanfile,
             "pkg2/src/pkg2.cpp": pkg2_source_cpp})

    tc.run("export pkg1")
    tc.run("export pkg2")
    tc.run("create pkg4")
    tc.run("create pkg3_1")
    tc.run("create pkg3_0")

    tc.run('create pkg1 -b="pkg1/*" -b="pkg2/*" -o="*:shared=True"')

    print()
