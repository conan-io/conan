import platform
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient

test = textwrap.dedent("""
    import os
    from conan import ConanFile, tools
    from conan.tools.build import can_run
    class TestApp(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "VirtualRunEnv"
        def requirements(self):
            self.requires(self.tested_reference_str)
        def test(self):
            if can_run(self):
                self.run("app", env="conanrun")
    """)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
@pytest.mark.parametrize("cppstd, cppstd_output, min_version", [
    ("gnu14", "__cplusplus201402", "11.0"),
    ("gnu17", "__cplusplus201703", "11.0"),
    ("gnu17", "__cplusplus201703", "10.15")
])
def test_project_xcodetoolchain(cppstd, cppstd_output, min_version):

    client = TestClient()
    client.run("new hello/0.1 -m=cmake_lib")
    client.run("export .")

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.apple import XcodeBuild
        from conan.tools.files import copy
        class MyApplicationConan(ConanFile):
            name = "myapplication"
            version = "1.0"
            requires = "hello/0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "XcodeDeps", "XcodeToolchain"
            exports_sources = "app.xcodeproj/*", "app/*"
            package_type = "application"
            def build(self):
                xcode = XcodeBuild(self)
                xcode.build("app.xcodeproj")
                self.run("otool -l build/{}/app".format(self.settings.build_type))

            def package(self):
                copy(self, "build/{}/app".format(self.settings.build_type), self.build_folder,
                     os.path.join(self.package_folder, "bin"), keep_path=False)

            def package_info(self):
                self.cpp_info.bindirs = ["bin"]
        """)

    xcode_project = textwrap.dedent("""
        name: app
        targets:
          app:
            type: tool
            platform: macOS
            sources:
              - app
            configFiles:
              Debug: conan_config.xcconfig
              Release: conan_config.xcconfig
        """)

    client.save({"conanfile.py": conanfile,
                 "test_package/conanfile.py": test,
                 "app/main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
                 "project.yml": xcode_project,
                 "conan_config.xcconfig": ""}, clean_first=True)

    client.run_command("xcodegen generate")

    sdk_version = "11.3"
    settings = "-s arch=x86_64 -s os.sdk=macosx -s os.sdk_version={} -s compiler.cppstd={} " \
               "-s compiler.libcxx=libc++ -s os.version={} " \
               "-c 'tools.build:cflags=[\"-fstack-protector-strong\"]'".format(sdk_version, cppstd, min_version)

    client.run("create . -s build_type=Release {} --build=missing".format(settings))
    assert "main __x86_64__ defined" in client.out
    assert "main {}".format(cppstd_output) in client.out
    assert "minos {}".format(min_version) in client.out
    assert "sdk {}".format(sdk_version) in client.out
    assert "libc++" in client.out
    assert " -fstack-protector-strong -" in client.out
