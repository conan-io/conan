import platform
import re
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_nmakedeps():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            name = "test-nmakedeps"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["pkg-1"].libs = ["pkg-1"]
                self.cpp_info.components["pkg-1"].defines = ["TEST_DEFINITION1"]
                self.cpp_info.components["pkg-1"].system_libs = ["ws2_32"]
                self.cpp_info.components["pkg-2"].libs = ["pkg-2"]
                self.cpp_info.components["pkg-2"].defines = ["TEST_DEFINITION2=0"]
                self.cpp_info.components["pkg-2"].requires = ["pkg-1"]
                self.cpp_info.components["pkg-3"].libs = ["pkg-3"]
                self.cpp_info.components["pkg-3"].defines = ["TEST_DEFINITION3="]
                self.cpp_info.components["pkg-3"].requires = ["pkg-1", "pkg-2"]
                self.cpp_info.components["pkg-4"].libs = ["pkg-4"]
                self.cpp_info.components["pkg-4"].defines = ["TEST_DEFINITION4=foo",
                                                            "TEST_DEFINITION5=__declspec(dllexport)",
                                                            "TEST_DEFINITION6=foo bar",
                                                            "TEST_DEFINITION7=7"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . -s arch=x86_64")
    client.run("install --requires=test-nmakedeps/1.0"
               " -g NMakeDeps -s build_type=Release -s arch=x86_64")
    # Checking that NMakeDeps builds correctly .bat file
    bat_file = client.load("conannmakedeps.bat")
    # Checking that defines are added to CL
    for flag in (
        '/D"TEST_DEFINITION1"', '/D"TEST_DEFINITION2#0"',
        '/D"TEST_DEFINITION3#"', '/D"TEST_DEFINITION4#"foo""',
        '/D"TEST_DEFINITION5#"__declspec\(dllexport\)""',
        '/D"TEST_DEFINITION6#"foo bar""',
        '/D"TEST_DEFINITION7#7"'
    ):
        assert re.search(fr'set "CL=%CL%.*\s{flag}(?:\s|")', bat_file)
    # Checking that libs and system libs are added to _LINK_
    for flag in (r"pkg-1\.lib", r"pkg-2\.lib", r"pkg-3\.lib", r"pkg-4\.lib", r"ws2_32\.lib"):
        assert re.search(fr'set "_LINK_=%_LINK_%.*\s{flag}(?:\s|")', bat_file)
