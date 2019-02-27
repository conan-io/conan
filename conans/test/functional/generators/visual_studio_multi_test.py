# coding=utf-8

import os
import platform
import unittest

from nose.plugins.attrib import attr
from parameterized import parameterized

from conans import MSBuild, tools
from conans.client.runner import ConanRunner
from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.test.utils.tools import TestClient
from conans.test.utils.visual_project_files import get_vs_project_files

main_cpp = r"""#include <hello.h>

int main()
{
    hello();
}
"""

conanfile_txt = r"""[requires]
Hello1/0.1@lasote/testing
[generators]
{generator}
"""

hello_conanfile_py = r"""from conans import ConanFile, CMake
import platform, os, shutil

class HelloConan(ConanFile):
    name = "Hello1"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"
    generators = "cmake"
    exports = '*'

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = ["hello"]
        self.cpp_info.debug.defines = ["CONAN_DEBUG"]
        self.cpp_info.release.defines = ["CONAN_RELEASE"]
"""

hello_cmake_lists_txt = r"""cmake_minimum_required(VERSION 2.8)
project(hello)

add_library(hello hello.cpp hello.h)
set_target_properties(hello PROPERTIES PUBLIC_HEADER "hello.h")
install(TARGETS hello
  LIBRARY DESTINATION "lib"
  ARCHIVE DESTINATION "lib"
  RUNTIME DESTINATION "lib"
  PUBLIC_HEADER DESTINATION "include")
"""

hello_h = r"""#pragma once

void hello_debug();
void hello_release();

#ifdef CONAN_DEBUG
#define hello hello_debug
#endif

#ifdef CONAN_RELEASE
#define hello hello_release
#endif
"""

hello_cpp = r"""#include "hello.h"

#include <iostream>

static void print_arch()
{{
#ifdef _M_IX86
    std::cout << "x86" << std::endl;
#endif
#ifdef _M_X64
    std::cout << "x64" << std::endl;
#endif
}}

void hello_release()
{{
    std::cout << "Hello Release" << std::endl;
    print_arch();
}}

void hello_debug()
{{
    std::cout << "Hello Debug" << std::endl;
    print_arch();
}}
"""


class VisualStudioMultiTest(unittest.TestCase):
    @parameterized.expand([("visual_studio", "conanbuildinfo.props"),
                           ("visual_studio_multi", "conanbuildinfo_multi.props")])
    @attr('slow')
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def build_vs_project_test(self, generator, props):
        client = TestClient()
        files = get_vs_project_files()
        files["MyProject/main.cpp"] = main_cpp
        files["conanfile.txt"] = conanfile_txt.format(generator=generator)
        files["hello/conanfile.py"] = hello_conanfile_py
        files["hello/CMakeLists.txt"] = hello_cmake_lists_txt
        files["hello/hello.h"] = hello_h
        files["hello/hello.cpp"] = hello_cpp

        props = os.path.join(client.current_folder, props)
        old = '<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />'
        new = old + '<Import Project="{props}" />'.format(props=props)
        files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)

        client.save(files, clean_first=True)

        client.run("export hello lasote/testing")

        for build_type in ["Debug", "Release"]:
            for arch in ["x86", "x86_64"]:
                runtime = "MDd" if build_type == "Debug" else "MD"
                settings = " -s os=Windows " \
                           " -s build_type={build_type} " \
                           " -s arch={arch}" \
                           " -s compiler=\"Visual Studio\"" \
                           " -s compiler.runtime={runtime}" \
                           " -s compiler.toolset=v141" \
                           " -s compiler.version=15".format(build_type=build_type, arch=arch,
                                                            runtime=runtime)

                client.run("install . {settings} --build missing".format(settings=settings))

                runner = ConanRunner(print_commands_to_output=True,
                                     generate_run_log_file=False,
                                     log_run_to_output=True)
                settings = MockSettings({"os": "Windows",
                                         "build_type": build_type,
                                         "arch": arch,
                                         "compiler": "Visual Studio",
                                         "compiler.runtime": runtime,
                                         "compiler.version": "15",
                                         "compiler.toolset": "v141"})
                conanfile = MockConanfile(settings, runner=runner)

                with tools.chdir(client.current_folder):
                    msbuild = MSBuild(conanfile)
                    msbuild.build(project_file="MyProject.sln", build_type=build_type, arch=arch)
