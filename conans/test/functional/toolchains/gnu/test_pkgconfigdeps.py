import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Needs pkg-config")
@pytest.mark.tool_pkg_config
def test_pkg_configdeps_definitions_escape():
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conans import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("USER_CONFIG=\"user_config.h\"")
                self.cpp_info.defines.append('OTHER="other.h"')
                self.cpp_info.cflags.append("flag1=\"my flag1\"")
                self.cpp_info.cxxflags.append('flag2="my flag2"')
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . hello/1.0@")
    client.save({"conanfile.txt": "[requires]\nhello/1.0\n"}, clean_first=True)
    client.run("install . --build=missing -g PkgConfigDeps")
    client.run_command("PKG_CONFIG_PATH=$(pwd) pkg-config --cflags hello")
    assert r'flag2=\"my flag2\" flag1=\"my flag1\" ' \
           r'-DUSER_CONFIG=\"user_config.h\" -DOTHER=\"other.h\"' in client.out
