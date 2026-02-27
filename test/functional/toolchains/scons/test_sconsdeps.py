import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux", reason="SCons functional tests"
                                                         "only for Linux")
@pytest.mark.tool("scons")
def test_sconsdeps():
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""\
        import os

        from conan import ConanFile
        from conan.tools.files import copy


        class helloConan(ConanFile):
            name = "hello"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            exports_sources = "src/*"

            # TODO: check what would be the correct layout and how to interact with
            # SCons scripts
            def layout(self):
                self.folders.source = "src"

            def build(self):
                debug_opt = '--debug-build' if self.settings.build_type == 'Debug' else ''
                self.run(f'scons -C {self.folders.source} {debug_opt}')

            def package(self):
                copy(self, pattern="*.h", dst=os.path.join(self.package_folder, "include"), src=os.path.join(self.source_folder),)
                copy(self, "*.lib", src=self.source_folder, dst=os.path.join(self.package_folder, "lib"), keep_path=False)
                copy(self, "*.a", src=self.source_folder, dst=os.path.join(self.package_folder, "lib"), keep_path=False)

            def package_info(self):
                self.cpp_info.libs = ["hello"]

        """)

    hello_cpp = textwrap.dedent("""\
        #include <iostream>
        #include "hello.h"

        void hello(){
            #ifdef NDEBUG
                std::cout << "Hello World Release!" <<std::endl;
            #else
                std::cout << "Hello World Debug!" <<std::endl;
            #endif
        }
        """)

    hello_h = textwrap.dedent("""\
        #pragma once

        #ifdef WIN32
          #define HELLO_EXPORT __declspec(dllexport)
        #else
          #define HELLO_EXPORT
        #endif

        HELLO_EXPORT void hello();
        """)

    sconscript = textwrap.dedent("""\
        import sys

        AddOption('--debug-build', action='store_true', help='debug build')

        env = Environment(TARGET_ARCH="x86_64")

        is_debug = GetOption('debug_build')
        is_release = not is_debug

        if not is_debug:
            env.Append(CPPDEFINES="NDEBUG")

        if is_debug:
            env.Append(CXXFLAGS = '-g -ggdb')
        else:
            env.Append(CXXFLAGS = '-O2')
            env.Append(LINKFLAGS = '-O2')

        env.Library("hello", "hello.cpp")
        """)

    sconstruct = textwrap.dedent("""\
        SConscript('SConscript', variant_dir='build', duplicate = False)
        """)

    t_sconscript = textwrap.dedent("""\
        import sys

        AddOption('--debug-build', action='store_true', help='debug build')

        env = Environment(TARGET_ARCH="x86_64")

        is_debug = GetOption('debug_build')
        is_release = not is_debug

        if not is_debug:
            env.Append(CPPDEFINES="NDEBUG")

        if is_debug:
            env.Append(CXXFLAGS = '-g -ggdb')
        else:
            env.Append(CXXFLAGS = '-O2')
            env.Append(LINKFLAGS = '-O2')

        build_path_relative_to_sconstruct = Dir('.').path

        conandeps = SConscript('./SConscript_conandeps')

        flags = conandeps["conandeps"]
        env.MergeFlags(flags)

        env.Program("main", "main.cpp")
        """)

    t_sconstruct = textwrap.dedent("""\
        SConscript('SConscript', variant_dir='build', duplicate = False)
        """)
    t_conanfile = textwrap.dedent("""\
        import os

        from conan import ConanFile

        class helloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "SConsDeps"
            apply_env = False
            test_type = "explicit"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                debug_opt = '--debug-build' if self.settings.build_type == 'Debug' else ''
                self.run(f'scons {debug_opt}')

            # TODO: check how to setup layout and scons
            def layout(self):
                self.folders.source = "."
                self.folders.generators = self.folders.source
                self.cpp.build.bindirs = ["build"]

            def test(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "main")
                self.run(cmd, env="conanrun")
        """)

    t_main_cpp = textwrap.dedent("""\
        #include "hello.h"

        int main() {
            hello();
        }
        """)

    client.save({"conanfile.py": conanfile,
                 "src/hello.cpp": hello_cpp,
                 "src/hello.h": hello_h,
                 "src/SConscript": sconscript,
                 "src/SConstruct": sconstruct,
                 "test_package/SConscript": t_sconscript,
                 "test_package/SConstruct": t_sconstruct,
                 "test_package/conanfile.py": t_conanfile,
                 "test_package/main.cpp": t_main_cpp,
                 })

    client.run("create .")
    assert "Hello World Release!" in client.out
