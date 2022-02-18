import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient

pbxproj = textwrap.dedent("""
    // !$*UTF8*$!
    {
        archiveVersion = 1;
        classes = {
        };
        objectVersion = 55;
        objects = {

    /* Begin PBXBuildFile section */
            07879B4027219EE500B6FB51 /* main.cpp in Sources */ = {isa = PBXBuildFile; fileRef = 07879B3F27219EE500B6FB51 /* main.cpp */; };
    /* End PBXBuildFile section */

    /* Begin PBXCopyFilesBuildPhase section */
            07879B3A27219EE500B6FB51 /* CopyFiles */ = {
                isa = PBXCopyFilesBuildPhase;
                buildActionMask = 2147483647;
                dstPath = /usr/share/man/man1/;
                dstSubfolderSpec = 0;
                files = (
                );
                runOnlyForDeploymentPostprocessing = 1;
            };
    /* End PBXCopyFilesBuildPhase section */

    /* Begin PBXFileReference section */
            07879B3C27219EE500B6FB51 /* app */ = {isa = PBXFileReference; explicitFileType = "compiled.mach-o.executable"; includeInIndex = 0; path = app; sourceTree = BUILT_PRODUCTS_DIR; };
            07879B3F27219EE500B6FB51 /* main.cpp */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.cpp.cpp; path = main.cpp; sourceTree = "<group>"; };
            41608B0827BBEB2800527FAA /* conandeps.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; name = conandeps.xcconfig; path = conandeps.xcconfig; sourceTree = SOURCE_ROOT; };
            41608B0927BBEB2800527FAA /* conan_hello_vars_release_x86_64.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; name = conan_hello_vars_release_x86_64.xcconfig; path = conan_hello_vars_release_x86_64.xcconfig; sourceTree = SOURCE_ROOT; };
            41608B0A27BBEB2900527FAA /* conan_hello_debug_x86_64.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; name = conan_hello_debug_x86_64.xcconfig; path = conan_hello_debug_x86_64.xcconfig; sourceTree = SOURCE_ROOT; };
            41608B0B27BBEB2900527FAA /* conan_hello.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; name = conan_hello.xcconfig; path = conan_hello.xcconfig; sourceTree = SOURCE_ROOT; };
            41608B0C27BBEB2900527FAA /* conan_hello_vars_debug_x86_64.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; name = conan_hello_vars_debug_x86_64.xcconfig; path = conan_hello_vars_debug_x86_64.xcconfig; sourceTree = SOURCE_ROOT; };
            41608B0D27BBEB2900527FAA /* conan_hello_release_x86_64.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; name = conan_hello_release_x86_64.xcconfig; path = conan_hello_release_x86_64.xcconfig; sourceTree = SOURCE_ROOT; };
    /* End PBXFileReference section */

    /* Begin PBXFrameworksBuildPhase section */
            07879B3927219EE500B6FB51 /* Frameworks */ = {
                isa = PBXFrameworksBuildPhase;
                buildActionMask = 2147483647;
                files = (
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
    /* End PBXFrameworksBuildPhase section */

    /* Begin PBXGroup section */
            07879B3327219EE500B6FB51 = {
                isa = PBXGroup;
                children = (
                    07879B3E27219EE500B6FB51 /* app */,
                    07879B3D27219EE500B6FB51 /* Products */,
                );
                sourceTree = "<group>";
            };
            07879B3D27219EE500B6FB51 /* Products */ = {
                isa = PBXGroup;
                children = (
                    07879B3C27219EE500B6FB51 /* app */,
                );
                name = Products;
                sourceTree = "<group>";
            };
            07879B3E27219EE500B6FB51 /* app */ = {
                isa = PBXGroup;
                children = (
                    41608B0A27BBEB2900527FAA /* conan_hello_debug_x86_64.xcconfig */,
                    41608B0D27BBEB2900527FAA /* conan_hello_release_x86_64.xcconfig */,
                    41608B0C27BBEB2900527FAA /* conan_hello_vars_debug_x86_64.xcconfig */,
                    41608B0927BBEB2800527FAA /* conan_hello_vars_release_x86_64.xcconfig */,
                    41608B0B27BBEB2900527FAA /* conan_hello.xcconfig */,
                    41608B0827BBEB2800527FAA /* conandeps.xcconfig */,
                    07879B3F27219EE500B6FB51 /* main.cpp */,
                );
                path = app;
                sourceTree = "<group>";
            };
    /* End PBXGroup section */

    /* Begin PBXNativeTarget section */
            07879B3B27219EE500B6FB51 /* app */ = {
                isa = PBXNativeTarget;
                buildConfigurationList = 07879B4327219EE500B6FB51 /* Build configuration list for PBXNativeTarget "app" */;
                buildPhases = (
                    07879B3827219EE500B6FB51 /* Sources */,
                    07879B3927219EE500B6FB51 /* Frameworks */,
                    07879B3A27219EE500B6FB51 /* CopyFiles */,
                );
                buildRules = (
                );
                dependencies = (
                );
                name = app;
                productName = app;
                productReference = 07879B3C27219EE500B6FB51 /* app */;
                productType = "com.apple.product-type.tool";
            };
    /* End PBXNativeTarget section */

    /* Begin PBXProject section */
            07879B3427219EE500B6FB51 /* Project object */ = {
                isa = PBXProject;
                attributes = {
                    BuildIndependentTargetsInParallel = 1;
                    LastUpgradeCheck = 1320;
                    TargetAttributes = {
                        07879B3B27219EE500B6FB51 = {
                            CreatedOnToolsVersion = 13.0;
                        };
                    };
                };
                buildConfigurationList = 07879B3727219EE500B6FB51 /* Build configuration list for PBXProject "app" */;
                compatibilityVersion = "Xcode 13.0";
                developmentRegion = en;
                hasScannedForEncodings = 0;
                knownRegions = (
                    en,
                    Base,
                );
                mainGroup = 07879B3327219EE500B6FB51;
                productRefGroup = 07879B3D27219EE500B6FB51 /* Products */;
                projectDirPath = "";
                projectRoot = "";
                targets = (
                    07879B3B27219EE500B6FB51 /* app */,
                );
            };
    /* End PBXProject section */

    /* Begin PBXSourcesBuildPhase section */
            07879B3827219EE500B6FB51 /* Sources */ = {
                isa = PBXSourcesBuildPhase;
                buildActionMask = 2147483647;
                files = (
                    07879B4027219EE500B6FB51 /* main.cpp in Sources */,
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
    /* End PBXSourcesBuildPhase section */

    /* Begin XCBuildConfiguration section */
            07879B4127219EE500B6FB51 /* Debug */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 41608B0827BBEB2800527FAA /* conandeps.xcconfig */;
                buildSettings = {
                    ALWAYS_SEARCH_USER_PATHS = NO;
                    CLANG_ANALYZER_NONNULL = YES;
                    CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
                    CLANG_CXX_LANGUAGE_STANDARD = "gnu++17";
                    CLANG_CXX_LIBRARY = "libc++";
                    CLANG_ENABLE_MODULES = YES;
                    CLANG_ENABLE_OBJC_ARC = YES;
                    CLANG_ENABLE_OBJC_WEAK = YES;
                    CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
                    CLANG_WARN_BOOL_CONVERSION = YES;
                    CLANG_WARN_COMMA = YES;
                    CLANG_WARN_CONSTANT_CONVERSION = YES;
                    CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
                    CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
                    CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
                    CLANG_WARN_EMPTY_BODY = YES;
                    CLANG_WARN_ENUM_CONVERSION = YES;
                    CLANG_WARN_INFINITE_RECURSION = YES;
                    CLANG_WARN_INT_CONVERSION = YES;
                    CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
                    CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
                    CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
                    CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
                    CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
                    CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
                    CLANG_WARN_STRICT_PROTOTYPES = YES;
                    CLANG_WARN_SUSPICIOUS_MOVE = YES;
                    CLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
                    CLANG_WARN_UNREACHABLE_CODE = YES;
                    CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
                    COPY_PHASE_STRIP = NO;
                    DEBUG_INFORMATION_FORMAT = dwarf;
                    ENABLE_STRICT_OBJC_MSGSEND = YES;
                    ENABLE_TESTABILITY = YES;
                    GCC_C_LANGUAGE_STANDARD = gnu11;
                    GCC_DYNAMIC_NO_PIC = NO;
                    GCC_NO_COMMON_BLOCKS = YES;
                    GCC_OPTIMIZATION_LEVEL = 0;
                    GCC_PREPROCESSOR_DEFINITIONS = (
                        "DEBUG=1",
                        "$(inherited)",
                    );
                    GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
                    GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
                    GCC_WARN_UNDECLARED_SELECTOR = YES;
                    GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
                    GCC_WARN_UNUSED_FUNCTION = YES;
                    GCC_WARN_UNUSED_VARIABLE = YES;
                    MACOSX_DEPLOYMENT_TARGET = 11.3;
                    MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
                    MTL_FAST_MATH = YES;
                    ONLY_ACTIVE_ARCH = YES;
                    SDKROOT = macosx;
                };
                name = Debug;
            };
            07879B4227219EE500B6FB51 /* Release */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 41608B0827BBEB2800527FAA /* conandeps.xcconfig */;
                buildSettings = {
                    ALWAYS_SEARCH_USER_PATHS = NO;
                    CLANG_ANALYZER_NONNULL = YES;
                    CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
                    CLANG_CXX_LANGUAGE_STANDARD = "gnu++17";
                    CLANG_CXX_LIBRARY = "libc++";
                    CLANG_ENABLE_MODULES = YES;
                    CLANG_ENABLE_OBJC_ARC = YES;
                    CLANG_ENABLE_OBJC_WEAK = YES;
                    CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
                    CLANG_WARN_BOOL_CONVERSION = YES;
                    CLANG_WARN_COMMA = YES;
                    CLANG_WARN_CONSTANT_CONVERSION = YES;
                    CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
                    CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
                    CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
                    CLANG_WARN_EMPTY_BODY = YES;
                    CLANG_WARN_ENUM_CONVERSION = YES;
                    CLANG_WARN_INFINITE_RECURSION = YES;
                    CLANG_WARN_INT_CONVERSION = YES;
                    CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
                    CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
                    CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
                    CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
                    CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
                    CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
                    CLANG_WARN_STRICT_PROTOTYPES = YES;
                    CLANG_WARN_SUSPICIOUS_MOVE = YES;
                    CLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
                    CLANG_WARN_UNREACHABLE_CODE = YES;
                    CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
                    COPY_PHASE_STRIP = NO;
                    DEBUG_INFORMATION_FORMAT = dwarf;
                    ENABLE_NS_ASSERTIONS = NO;
                    ENABLE_STRICT_OBJC_MSGSEND = YES;
                    GCC_C_LANGUAGE_STANDARD = gnu11;
                    GCC_NO_COMMON_BLOCKS = YES;
                    GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
                    GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
                    GCC_WARN_UNDECLARED_SELECTOR = YES;
                    GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
                    GCC_WARN_UNUSED_FUNCTION = YES;
                    GCC_WARN_UNUSED_VARIABLE = YES;
                    MACOSX_DEPLOYMENT_TARGET = 11.3;
                    MTL_ENABLE_DEBUG_INFO = NO;
                    MTL_FAST_MATH = YES;
                    SDKROOT = macosx;
                };
                name = Release;
            };
            07879B4427219EE500B6FB51 /* Debug */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 41608B0827BBEB2800527FAA /* conandeps.xcconfig */;
                buildSettings = {
                    CODE_SIGN_IDENTITY = "-";
                    CODE_SIGN_STYLE = Automatic;
                    PRODUCT_NAME = "$(TARGET_NAME)";
                };
                name = Debug;
            };
            07879B4527219EE500B6FB51 /* Release */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 41608B0827BBEB2800527FAA /* conandeps.xcconfig */;
                buildSettings = {
                    CODE_SIGN_IDENTITY = "-";
                    CODE_SIGN_STYLE = Automatic;
                    PRODUCT_NAME = "$(TARGET_NAME)";
                };
                name = Release;
            };
    /* End XCBuildConfiguration section */

    /* Begin XCConfigurationList section */
            07879B3727219EE500B6FB51 /* Build configuration list for PBXProject "app" */ = {
                isa = XCConfigurationList;
                buildConfigurations = (
                    07879B4127219EE500B6FB51 /* Debug */,
                    07879B4227219EE500B6FB51 /* Release */,
                );
                defaultConfigurationIsVisible = 0;
                defaultConfigurationName = Release;
            };
            07879B4327219EE500B6FB51 /* Build configuration list for PBXNativeTarget "app" */ = {
                isa = XCConfigurationList;
                buildConfigurations = (
                    07879B4427219EE500B6FB51 /* Debug */,
                    07879B4527219EE500B6FB51 /* Release */,
                );
                defaultConfigurationIsVisible = 0;
                defaultConfigurationName = Release;
            };
    /* End XCConfigurationList section */
        };
        rootObject = 07879B3427219EE500B6FB51 /* Project object */;
    }
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
    from conans import ConanFile, tools
    class TestApp(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "VirtualRunEnv"
        def test(self):
            if not tools.cross_building(self):
                self.run("app", env="conanrun")
    """)


@pytest.fixture(scope="module")
def client():
    client = TestClient()
    client.run("new hello/0.1 -m=cmake_lib")
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")
    return client


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
def test_project_xcodebuild(client):

    conanfile = textwrap.dedent("""
        from conans import ConanFile
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

            def package(self):
                self.copy("*/app", dst="bin", src=".", keep_path=False)

            def package_info(self):
                self.cpp_info.bindirs = ["bin"]
        """)

    client.save({"conanfile.py": conanfile,
                 "test_package/conanfile.py": test,
                 "app/main.cpp": main,
                 "app.xcodeproj/project.pbxproj": pbxproj}, clean_first=True)
    client.run("create . --build=missing")
    assert "hello/0.1: Hello World Release!" in client.out
    assert "App Release!" in client.out
    client.run("create . -s build_type=Debug --build=missing")
    assert "hello/0.1: Hello World Debug!" in client.out
    assert "App Debug!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
@pytest.mark.skip(reason="Different sdks not installed in CI")
def test_xcodebuild_test_different_sdk(client):

    conanfile = textwrap.dedent("""
        from conans import ConanFile
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
                 "app.xcodeproj/project.pbxproj": pbxproj}, clean_first=True)
    client.run("create . --build=missing -s os.sdk=macosx -s os.sdk_version=10.15 "
               "-c tools.apple:sdk_path='/Applications/Xcode11.7.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.15.sdk'")
    assert "sdk 10.15.6" in client.out
    client.run("create . --build=missing -s os.sdk=macosx -s os.sdk_version=11.3 "
               "-c tools.apple:sdk_path='/Applications/Xcode12.5.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX11.3.sdk'")
    assert "sdk 11.3" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
def test_missing_sdk(client):

    conanfile = textwrap.dedent("""
        from conans import ConanFile
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
                 "app.xcodeproj/project.pbxproj": pbxproj}, clean_first=True)
    client.run("create . --build=missing -s os.sdk=macosx -s os.sdk_version=12.0 "
               "-c tools.apple:sdk_path=notexistingsdk", assert_error=True)
