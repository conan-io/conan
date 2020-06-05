# coding=utf-8

import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient

from conans import MesonX

@attr("toolchain")
class Base(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conans import ConanFile, MesonX, MesonDefaultToolchain, MesonMachineFile, tools
        from configparser import ConfigParser

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "pkg_config"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            def toolchain(self):
                tc = MesonDefaultToolchain(self)

                config = ConfigParser()
                config.read_dict({
                    "properties": {
                        "user_option": '"FOO"'
                    }
                })

                machine_file = MesonMachineFile(name="user_override", config=config)
                if tools.cross_building(self.settings):
                    tc.cross_files += [machine_file]
                else:
                    tc.native_files += [machine_file]
                return tc

            def build(self):
                meson = MesonX(self)
                meson.configure(source_subdir="src")
                meson.build()
        """)

    lib_h = textwrap.dedent("""
        #pragma once
        #ifdef WIN32
          #define APP_LIB_EXPORT __declspec(dllexport)
        #else
          #define APP_LIB_EXPORT
        #endif
        APP_LIB_EXPORT void app();
        """)

    lib_cpp = textwrap.dedent("""
        #include <iostream>
        #include "app.h"
        #include "hello.h"

        void app() {
            std::cout << "Hello: " << HELLO_MSG << std::endl;
            #ifdef NDEBUG
            std::cout << "App: Release!" <<std::endl;
            #else
            std::cout << "App: Debug!" <<std::endl;
            #endif
            std::cout << "USER_OPTION_VALUE: " << USER_OPTION_VALUE << "\\n";
        }
        """)

    app = textwrap.dedent("""
        #include "app.h"

        int main() {
            app();
        }
        """)

    meson = textwrap.dedent("""
        project('test','cpp')
        
        message('>> buildtype:', get_option('buildtype'))
        message('>> cpp_std:', get_option('cpp_std'))
        message('>> b_staticpic:', get_option('b_staticpic'))
        message('>> prefix:', get_option('prefix'))
        message('>> default_library:', get_option('default_library'))

        dep_hello = dependency('hello', method: 'pkg-config', include_type: 'system')

        cpp_flags_lib = []
        user_option_value = meson.get_external_property('user_option', '')
        if user_option_value != ''
            cpp_flags_lib += ['-DUSER_OPTION_VALUE="' + user_option_value + '"']
        endif

        lib_app_lib = library(
            'app_lib', 
            sources: ['app_lib.cpp'],
            cpp_args: cpp_flags_lib,
            dependencies: dep_hello
        )

        exe_app = executable(
            'app', 
            sources: ['app.cpp'],
            link_with: lib_app_lib
        )
        """)

    def setUp(self):
        self.client = TestClient(path_with_spaces=False)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import save
            import os
            class Pkg(ConanFile):
                settings = "build_type"
                generators = "pkg_config"

                def package(self):
                    save(os.path.join(self.package_folder, "include/hello.h"),
                         '#define HELLO_MSG "%s"' % self.settings.build_type)
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . hello/0.1@ -s build_type=Debug")
        self.client.run("create . hello/0.1@ -s build_type=Release")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "src/meson.build": self.meson,
                          "src/app.cpp": self.app,
                          "src/app_lib.cpp": self.lib_cpp,
                          "src/app.h": self.lib_h})

    def _run_build(self, settings=None, options=None):
        # Build the profile according to the settings provided
        settings = settings or {}
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        options = " ".join("-o %s=%s" % (k, v) for k, v in options.items()) if options else ""

        # Run the configure corresponding to this test case
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("install .. %s %s" % (settings, options))
            install_out = self.client.out
            self.client.run("build ..")
        return install_out

@unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
class LinuxTest(Base):
    @parameterized.expand([("Debug",  "14", "x86", "libstdc++", True),
                           ("Release", "gnu14", "x86_64", "libstdc++11", False)])
    def test_toolchain_linux(self, build_type, cppstd, arch, libcxx, shared):
        settings = {"compiler": "gcc",
                    "compiler.cppstd": cppstd,
                    "compiler.libcxx": libcxx,
                    "arch": arch,
                    "build_type": build_type}
        self._run_build(settings, {"shared": shared})

        #self.assertIn('CMake command: cmake -G "Unix Makefiles" '
                      #'-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
        if shared:
            self.assertIn("libapp_lib.so", self.client.out)
        else:
            self.assertIn("libapp_lib.a", self.client.out)

        out = str(self.client.out).splitlines()
        shared_str = "shared" if shared else "static"
        vals = {"cpp_std": MesonX._get_meson_cppstd(cppstd),
                "buildtype": MesonX._get_meson_buildtype(build_type),
                "b_staticpic": "True", # True by default
                "default_library": shared_str,
                }
        for k, v in vals.items():
            self.assertIn("Message: >> %s: %s" % (k, v), out)

        self.client.run_command("build/app")
        self.assertIn("Hello: %s" % build_type, self.client.out)
        self.assertIn("App: %s!" % build_type, self.client.out)
        self.assertIn("USER_OPTION_VALUE: FOO", self.client.out)

@attr("toolchain")
class MesonInstallTest(unittest.TestCase):

    def test_install(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, MesonX

            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                exports_sources = "src/meson.build", "src/header.h"

                generators = "pkg_config"
                toolchain = "meson"

                def build(self):
                    meson = MesonX(self)
                    meson.configure(source_subdir="src")

                def package(self):
                    meson = MesonX(self)
                    meson.install()
            """)

        meson = textwrap.dedent("""
            project('App C', 'c')

            src_inc_files = files('header.h')
            install_headers(src_inc_files, install_dir: 'include')
            """)
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile,
                     "src/meson.build": meson,
                     "src/header.h": "# my header file"})

        # FIXME: This is broken, because the toolchain at install time, doesn't have the package
        # folder yet. We need to define the layout for local development
        """
        with client.chdir("build"):
            client.run("install ..")
            client.run("build ..")
            client.run("package .. -pf=mypkg")  # -pf=mypkg ignored
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build",
                                                    "include", "header.h")))"""

        # The create flow must work
        client.run("create . pkg/0.1@")
        self.assertIn("pkg/0.1 package(): Packaged 1 '.h' file: header.h", client.out)
        ref = ConanFileReference.loads("pkg/0.1")
        layout = client.cache.package_layout(ref)
        package_id = layout.conan_packages()[0]
        package_folder = layout.package(PackageReference(ref, package_id))
        self.assertTrue(os.path.exists(os.path.join(package_folder, "include", "header.h")))
