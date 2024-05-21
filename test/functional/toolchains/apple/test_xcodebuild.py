import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient

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

main = textwrap.dedent("""
    #include <iostream>
    #include "hello.h"
    int main(int argc, char *argv[]) {
        hello();
        #ifndef DEBUG
        std::cout << "App Release!" << std::endl;
        #else
        std::cout << "App Debug!" << std::endl;
        #endif
    }
    """)

test = textwrap.dedent("""
    import os
    from conan import ConanFile, tools
    from conan.tools.build import cross_building
    class TestApp(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        def requirements(self):
            self.requires(self.tested_reference_str)
        def test(self):
            if not cross_building(self):
                self.run("app", env="conanrun")
    """)


@pytest.fixture(scope="module")
def client():
    client = TestClient()
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")
    return client


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool("xcodebuild")
@pytest.mark.tool("xcodegen")
def test_project_xcodebuild(client):

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
            generators = "XcodeDeps"
            exports_sources = "app.xcodeproj/*", "app/*"
            package_type = "application"
            def build(self):
                xcode = XcodeBuild(self)
                xcode.build("app.xcodeproj")

            def package(self):
                copy(self, "build/{}/app".format(self.settings.build_type), self.source_folder,
                     os.path.join(self.package_folder, "bin"), keep_path=False)

            def package_info(self):
                self.cpp_info.bindirs = ["bin"]
        """)

    client.save({"conanfile.py": conanfile,
                 "test_package/conanfile.py": test,
                 "app/main.cpp": main,
                 "project.yml": xcode_project}, clean_first=True)
    client.run("install . --build=missing")
    client.run("install . -s build_type=Debug --build=missing")
    client.run_command("xcodegen generate")
    client.run("create . --build=missing -c tools.build:verbosity=verbose -c tools.compilation:verbosity=verbose")
    assert "xcodebuild: error: invalid option" not in client.out
    assert "hello/0.1: Hello World Release!" in client.out
    assert "App Release!" in client.out
    client.run("create . -s build_type=Debug --build=missing")
    assert "hello/0.1: Hello World Debug!" in client.out
    assert "App Debug!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool("xcodebuild")
@pytest.mark.tool("xcodegen")
@pytest.mark.skip(reason="Different sdks not installed in CI")
def test_xcodebuild_test_different_sdk(client):

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.apple import XcodeBuild
        class MyApplicationConan(ConanFile):
            name = "myapplication"
            version = "1.0"
            requires = "hello/0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "XcodeDeps"
            exports_sources = "app.xcodeproj/*", "app/*"
            def build(self):
                xcode = XcodeBuild(self)
                xcode.build("app.xcodeproj")
                self.run("otool -l build/Release/app")
        """)

    client.save({"conanfile.py": conanfile,
                 "app/main.cpp": main,
                 "project.yml": xcode_project}, clean_first=True)
    client.run("install . --build=missing")
    client.run("install . -s build_type=Debug --build=missing")
    client.run_command("xcodegen generate")
    client.run("create . --build=missing -s os.sdk=macosx -s os.sdk_version=10.15 "
               "-c tools.apple:sdk_path='/Applications/Xcode11.7.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.15.sdk'")
    assert "sdk 10.15.6" in client.out
    client.run("create . --build=missing -s os.sdk_version=11.3 "
               "-c tools.apple:sdk_path='/Applications/Xcode12.5.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX11.3.sdk'")
    assert "sdk 11.3" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool("xcodebuild")
@pytest.mark.tool("xcodegen")
def test_missing_sdk(client):

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.apple import XcodeBuild
        class MyApplicationConan(ConanFile):
            name = "myapplication"
            version = "1.0"
            requires = "hello/0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "XcodeDeps"
            exports_sources = "app.xcodeproj/*", "app/*"
            def build(self):
                xcode = XcodeBuild(self)
                xcode.build("app.xcodeproj")
        """)

    client.save({"conanfile.py": conanfile,
                 "app/main.cpp": main,
                 "project.yml": xcode_project}, clean_first=True)
    client.run("install . --build=missing")
    client.run("install . -s build_type=Debug --build=missing")
    client.run_command("xcodegen generate")
    client.run("create . --build=missing -s os.sdk=macosx -s os.sdk_version=12.0 "
               "-c tools.apple:sdk_path=notexistingsdk", assert_error=True)
