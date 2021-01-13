# coding=utf-8

import os
import platform
import unittest

import pytest
from parameterized import parameterized

from conans import MSBuild, tools
from conans.client.runner import ConanRunner
from conans.test.utils.mocks import MockSettings, MockConanfile, TestBufferConanOutput
from conans.test.utils.tools import TestClient
from conans.test.assets.visual_project_files import get_vs_project_files

main_cpp = r"""#include <hello.h>

int main(){
    hello();
}
"""

conanfile_txt = r"""[requires]
Hello1/0.1@lasote/testing
[generators]
{generator}
"""

hello_conanfile_py = r"""from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello1"
    version = "0.1"
    exports = '*'

    def package(self):
        self.copy("*.h", dst="include")

    def package_info(self):
        self.cpp_info.debug.defines = ["CONAN_DEBUG"]
        self.cpp_info.release.defines = ["CONAN_RELEASE"]
"""


hello_h = r"""#include <iostream>

#ifdef CONAN_DEBUG
void hello(){
    std::cout << "Hello Debug!!!" << std::endl;
}
#endif
#ifdef CONAN_RELEASE
void hello(){
    std::cout << "Hello Release!!!" << std::endl;
}
#endif
"""


@pytest.mark.slow
@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
class VisualStudioMultiTest(unittest.TestCase):

    @parameterized.expand([("visual_studio", "conanbuildinfo.props"),
                           ("visual_studio_multi", "conanbuildinfo_multi.props")])
    def test_build_vs_project(self, generator, props):
        client = TestClient()
        client.save({"conanfile.py": hello_conanfile_py,
                     "hello.h": hello_h})
        client.run("create . lasote/testing")

        files = get_vs_project_files()
        files["MyProject/main.cpp"] = main_cpp
        files["conanfile.txt"] = conanfile_txt.format(generator=generator)
        props = os.path.join(client.current_folder, props)
        old = r'<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />'
        new = old + '<Import Project="{props}" />'.format(props=props)
        files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)
        client.save(files, clean_first=True)

        for build_type in ["Debug", "Release"]:
            arch = "x86"
            runner = ConanRunner(print_commands_to_output=True,
                                 generate_run_log_file=False,
                                 log_run_to_output=True,
                                 output=TestBufferConanOutput())
            settings = MockSettings({"os": "Windows",
                                     "build_type": build_type,
                                     "arch": arch,
                                     "compiler": "Visual Studio",
                                     "compiler.version": "15",
                                     "compiler.toolset": "v141"})
            conanfile = MockConanfile(settings, runner=runner)
            settings = " -s os=Windows " \
                       " -s build_type={build_type} " \
                       " -s arch={arch}" \
                       " -s compiler=\"Visual Studio\"" \
                       " -s compiler.toolset=v141" \
                       " -s compiler.version=15".format(build_type=build_type, arch=arch)
            client.run("install . %s" % settings)
            with tools.chdir(client.current_folder):
                msbuild = MSBuild(conanfile)
                msbuild.build(project_file="MyProject.sln", build_type=build_type, arch=arch)
                output = TestBufferConanOutput()
                client.run_command(r"%s\MyProject.exe" % build_type)
                self.assertIn("Hello %s!!!" % build_type, client.out)
