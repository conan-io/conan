import os
import textwrap
from xml.dom import minidom

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.parametrize(
    "arch,exp_platform",
    [
        ("x86", "Win32"),
        ("x86_64", "x64"),
        ("armv7", "ARM"),
        ("armv8", "ARM64"),
    ],
)
def test_msbuilddeps_maps_architecture_to_platform(arch, exp_platform):
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=msbuild_lib")
    client.run(f"install . -g MSBuildDeps -s arch={arch} -pr:b=default -if=install")
    toolchain = client.load(os.path.join("conan", "conantoolchain.props"))
    expected_import = f"""<Import Condition="'$(Configuration)' == 'Release' And '$(Platform)' == '{exp_platform}'" Project="conantoolchain_release_{exp_platform.lower()}.props"/>"""
    assert expected_import in toolchain


def test_msbuilddeps_format_names():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg.name-more+"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["libmpdecimal++"].libs = ["libmp++"]
                self.cpp_info.components["mycomp.some-comp+"].libs = ["mylib"]
                self.cpp_info.components["libmpdecimal++"].requires = ["mycomp.some-comp+"]
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create . -s arch=x86_64")
    # Issue: https://github.com/conan-io/conan/issues/11822
    c.run("install pkg.name-more+/1.0@ -g MSBuildDeps -s build_type=Release -s arch=x86_64")
    # Checking that MSBuildDeps builds correctly the XML file
    # loading all .props and xml parse them to check no errors
    counter = 0
    for f in os.listdir(c.current_folder):
        if f.endswith(".props"):
            content = c.load(f)
            minidom.parseString(content)
            counter += 1
    assert counter == 8
