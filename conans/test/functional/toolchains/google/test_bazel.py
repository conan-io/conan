import os
import platform
import textwrap
import time
import unittest

import pytest

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@pytest.mark.tool("bazel")
class Base(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conan.tools.google import Bazel
        from conan import ConanFile

        class App(ConanFile):
            name="test_bazel_app"
            version="0.0"
            settings = "os", "compiler", "build_type", "arch"
            generators = "BazelDeps", "BazelToolchain"
            exports_sources = "WORKSPACE", "app/*"

            def build(self):
                bazel = Bazel(self)
                bazel.configure()
                bazel.build(label="//app:main")

            def package(self):
                self.copy('*', src='bazel-bin')
        """)

    buildfile = textwrap.dedent("""
    load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library")

    cc_library(
        name = "hello",
        srcs = ["hello.cpp"],
        hdrs = ["hello.h",],
    )

    cc_binary(
        name = "main",
        srcs = ["main.cpp"],
        deps = [":hello"],
    )
""")

    lib_h = gen_function_h(name="hello")
    lib_cpp = gen_function_cpp(name="hello", msg="Hello", includes=["hello"])
    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    workspace_file = textwrap.dedent("""
    load("@//bazel-build/conandeps:dependencies.bzl", "load_conan_dependencies")
    load_conan_dependencies()
    """)

    def setUp(self):
        self.client = TestClient(path_with_spaces=False)  # bazel doesn't work with paths with spaces
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conans.tools import save
            import os
            class Pkg(ConanFile):
                settings = "build_type"
                def package(self):
                    save(os.path.join(self.package_folder, "include/hello.h"),
                         '''#include <iostream>
                         void hello(){std::cout<< "Hello: %s" <<std::endl;}'''
                         % self.settings.build_type)
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . --name=hello --version=0.1 -s build_type=Debug")
        self.client.run("create . --name=hello --version=0.1 -s build_type=Release")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "WORKSPACE": self.workspace_file,
                          "app/BUILD": self.buildfile,
                          "app/main.cpp": self.main,
                          "app/hello.cpp": self.lib_cpp,
                          "app/hello.h": self.lib_h})

    def _run_build(self):
        build_directory = os.path.join(self.client.current_folder, "bazel-build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("install .. ")
            install_out = self.client.out
            self.client.run("build ..")
        return install_out

    def _modify_code(self):
        lib_cpp = gen_function_cpp(name="hello", msg="HelloImproved", includes=["hello"])
        self.client.save({"app/hello.cpp": lib_cpp})

    def _incremental_build(self):
        with self.client.chdir(self.client.current_folder):
            self.client.run_command("bazel build --explain=output.txt //app:main")

    def _run_app(self, bin_folder=False):
        command_str = "bazel-bin/app/main.exe" if bin_folder else "bazel-bin/app/main"
        if platform.system() == "Windows":
            command_str = command_str.replace("/", "\\")

        self.client.run_command(command_str)


@pytest.mark.skipif(platform.system() == "Darwin", reason="Test failing randomly in macOS")
class BazelToolchainTest(Base):

    def test_toolchain(self):
        # FIXME: THis is using "Debug" by default, it should be release, but it
        #  depends completely on the external bazel files, the toolchain does not do it
        build_type = "Debug"
        self._run_build()

        self.assertIn("INFO: Build completed successfully", self.client.out)

        self._run_app()
        self.assertIn("%s: %s!" % ("Hello", build_type), self.client.out)

        self._modify_code()
        time.sleep(1)
        self._incremental_build()
        rebuild_info = self.client.load("output.txt")
        text_to_find = "'Compiling app/hello.cpp': One of the files has changed."
        self.assertIn(text_to_find, rebuild_info)

        self._run_app()
        self.assertIn("%s: %s!" % ("HelloImproved", build_type), self.client.out)
