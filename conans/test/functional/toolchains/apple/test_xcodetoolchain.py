import platform
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp
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
            4130DB5F27BE8D0300BDEE84 /* conan_hello_release_x86_64_macosx_12_1.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_hello_release_x86_64_macosx_12_1.xcconfig; sourceTree = "<group>"; };
            4130DB6027BE8D0300BDEE84 /* conan_hello_vars_debug_x86_64_macosx_12_1.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_hello_vars_debug_x86_64_macosx_12_1.xcconfig; sourceTree = "<group>"; };
            4130DB6127BE8D0300BDEE84 /* conantoolchain_debug_x86_64_macosx_12_1.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conantoolchain_debug_x86_64_macosx_12_1.xcconfig; sourceTree = "<group>"; };
            4130DB6227BE8D0300BDEE84 /* conantoolchain_release_x86_64_macosx_12_1.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conantoolchain_release_x86_64_macosx_12_1.xcconfig; sourceTree = "<group>"; };
            4130DB6327BE8D0300BDEE84 /* conan_hello.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_hello.xcconfig; sourceTree = "<group>"; };
            4130DB6427BE8D0300BDEE84 /* conan_hello_vars_release_x86_64_macosx_12_1.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_hello_vars_release_x86_64_macosx_12_1.xcconfig; sourceTree = "<group>"; };
            4130DB6527BE8D0300BDEE84 /* conan_hello_debug_x86_64_macosx_12_1.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_hello_debug_x86_64_macosx_12_1.xcconfig; sourceTree = "<group>"; };
            4130DB6627BE8D0300BDEE84 /* conan_config.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_config.xcconfig; sourceTree = "<group>"; };
            4130DB6727BE8D0300BDEE84 /* conantoolchain.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conantoolchain.xcconfig; sourceTree = "<group>"; };
            4130DB6827BE8D0300BDEE84 /* conandeps.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conandeps.xcconfig; sourceTree = "<group>"; };
            416ED66527F1FFAE00664526 /* conan_global_flags.xcconfig */ = {isa = PBXFileReference; lastKnownFileType = text.xcconfig; path = conan_global_flags.xcconfig; sourceTree = "<group>"; };
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
                    4130DB6927BE8D0D00BDEE84 /* conan */,
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
                    07879B3F27219EE500B6FB51 /* main.cpp */,
                );
                path = app;
                sourceTree = "<group>";
            };
            4130DB6927BE8D0D00BDEE84 /* conan */ = {
                isa = PBXGroup;
                children = (
                    416ED66527F1FFAE00664526 /* conan_global_flags.xcconfig */,
                    4130DB6627BE8D0300BDEE84 /* conan_config.xcconfig */,
                    4130DB6527BE8D0300BDEE84 /* conan_hello_debug_x86_64_macosx_12_1.xcconfig */,
                    4130DB5F27BE8D0300BDEE84 /* conan_hello_release_x86_64_macosx_12_1.xcconfig */,
                    4130DB6027BE8D0300BDEE84 /* conan_hello_vars_debug_x86_64_macosx_12_1.xcconfig */,
                    4130DB6427BE8D0300BDEE84 /* conan_hello_vars_release_x86_64_macosx_12_1.xcconfig */,
                    4130DB6327BE8D0300BDEE84 /* conan_hello.xcconfig */,
                    4130DB6827BE8D0300BDEE84 /* conandeps.xcconfig */,
                    4130DB6127BE8D0300BDEE84 /* conantoolchain_debug_x86_64_macosx_12_1.xcconfig */,
                    4130DB6227BE8D0300BDEE84 /* conantoolchain_release_x86_64_macosx_12_1.xcconfig */,
                    4130DB6727BE8D0300BDEE84 /* conantoolchain.xcconfig */,
                );
                name = conan;
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
                baseConfigurationReference = 4130DB6627BE8D0300BDEE84 /* conan_config.xcconfig */;
                buildSettings = {
                    ALWAYS_SEARCH_USER_PATHS = NO;
                    ARCHS = x86_64;
                    CLANG_ANALYZER_NONNULL = YES;
                    CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
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
                    MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
                    MTL_FAST_MATH = YES;
                    ONLY_ACTIVE_ARCH = YES;
                    SDKROOT = macosx12.1;
                };
                name = Debug;
            };
            07879B4227219EE500B6FB51 /* Release */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 4130DB6627BE8D0300BDEE84 /* conan_config.xcconfig */;
                buildSettings = {
                    ALWAYS_SEARCH_USER_PATHS = NO;
                    ARCHS = x86_64;
                    CLANG_ANALYZER_NONNULL = YES;
                    CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
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
                    MTL_ENABLE_DEBUG_INFO = NO;
                    MTL_FAST_MATH = YES;
                    ONLY_ACTIVE_ARCH = YES;
                    SDKROOT = macosx12.1;
                };
                name = Release;
            };
            07879B4427219EE500B6FB51 /* Debug */ = {
                isa = XCBuildConfiguration;
                buildSettings = {
                    CODE_SIGN_IDENTITY = "-";
                    CODE_SIGN_STYLE = Automatic;
                    PRODUCT_NAME = "$(TARGET_NAME)";
                };
                name = Debug;
            };
            07879B4527219EE500B6FB51 /* Release */ = {
                isa = XCBuildConfiguration;
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
        from conans import ConanFile
        from conan.tools.apple import XcodeBuild
        class MyApplicationConan(ConanFile):
            name = "myapplication"
            version = "1.0"
            requires = "hello/0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "XcodeDeps", "XcodeToolchain"
            exports_sources = "app.xcodeproj/*", "app/*"
            def build(self):
                xcode = XcodeBuild(self)
                xcode.build("app.xcodeproj")
                self.run("otool -l build/{}/app".format(self.settings.build_type))

            def package(self):
                self.copy("*/app", dst="bin", src=".", keep_path=False)

            def package_info(self):
                self.cpp_info.bindirs = ["bin"]
        """)

    client.save({"conanfile.py": conanfile,
                 "test_package/conanfile.py": test,
                 "app/main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
                 "app.xcodeproj/project.pbxproj": pbxproj}, clean_first=True)

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
