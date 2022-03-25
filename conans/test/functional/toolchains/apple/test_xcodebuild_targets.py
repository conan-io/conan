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
            4102E02127E0F84800A6AD9D /* hello.cpp in Sources */ = {isa = PBXBuildFile; fileRef = 4102E01F27E0F84800A6AD9D /* hello.cpp */; };
            4102E02227E0F84800A6AD9D /* hello.hpp in Headers */ = {isa = PBXBuildFile; fileRef = 4102E02027E0F84800A6AD9D /* hello.hpp */; };
            4102E03627E1027F00A6AD9D /* hello.hpp in Headers */ = {isa = PBXBuildFile; fileRef = 4102E02027E0F84800A6AD9D /* hello.hpp */; };
            4102E03827E1027F00A6AD9D /* hello.cpp in Sources */ = {isa = PBXBuildFile; fileRef = 4102E01F27E0F84800A6AD9D /* hello.cpp */; };
    /* End PBXBuildFile section */

    /* Begin PBXFileReference section */
            4102E01827E0F83900A6AD9D /* libhello.dylib */ = {isa = PBXFileReference; explicitFileType = archive.ar; includeInIndex = 0; path = libhello.dylib; sourceTree = BUILT_PRODUCTS_DIR; };
            4102E01F27E0F84800A6AD9D /* hello.cpp */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.cpp.cpp; path = hello.cpp; sourceTree = "<group>"; };
            4102E02027E0F84800A6AD9D /* hello.hpp */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.cpp.h; path = hello.hpp; sourceTree = "<group>"; };
            4102E03D27E1027F00A6AD9D /* libhello.a */ = {isa = PBXFileReference; explicitFileType = archive.ar; includeInIndex = 0; path = libhello.a; sourceTree = BUILT_PRODUCTS_DIR; };
            4102E03E27E1CEB000A6AD9D /* conan_config.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conan_config.xcconfig; sourceTree = "<group>"; };
            4102E03F27E1CEB000A6AD9D /* conantoolchain_release_x86_64.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conantoolchain_release_x86_64.xcconfig; sourceTree = "<group>"; };
            4102E04027E1CEB000A6AD9D /* conantoolchain.xcconfig */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.xcconfig; path = conantoolchain.xcconfig; sourceTree = "<group>"; };
    /* End PBXFileReference section */

    /* Begin PBXFrameworksBuildPhase section */
            4102E01627E0F83900A6AD9D /* Frameworks */ = {
                isa = PBXFrameworksBuildPhase;
                buildActionMask = 2147483647;
                files = (
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
            4102E03927E1027F00A6AD9D /* Frameworks */ = {
                isa = PBXFrameworksBuildPhase;
                buildActionMask = 2147483647;
                files = (
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
    /* End PBXFrameworksBuildPhase section */

    /* Begin PBXGroup section */
            4102E00F27E0F83900A6AD9D = {
                isa = PBXGroup;
                children = (
                    4102E03E27E1CEB000A6AD9D /* conan_config.xcconfig */,
                    4102E03F27E1CEB000A6AD9D /* conantoolchain_release_x86_64.xcconfig */,
                    4102E04027E1CEB000A6AD9D /* conantoolchain.xcconfig */,
                    4102E02327E0F99200A6AD9D /* src */,
                    4102E01927E0F83900A6AD9D /* Products */,
                );
                sourceTree = "<group>";
            };
            4102E01927E0F83900A6AD9D /* Products */ = {
                isa = PBXGroup;
                children = (
                    4102E01827E0F83900A6AD9D /* libhello.dylib */,
                    4102E03D27E1027F00A6AD9D /* libhello.a */,
                );
                name = Products;
                sourceTree = "<group>";
            };
            4102E02327E0F99200A6AD9D /* src */ = {
                isa = PBXGroup;
                children = (
                    4102E01F27E0F84800A6AD9D /* hello.cpp */,
                    4102E02027E0F84800A6AD9D /* hello.hpp */,
                );
                path = src;
                sourceTree = "<group>";
            };
    /* End PBXGroup section */

    /* Begin PBXHeadersBuildPhase section */
            4102E01427E0F83900A6AD9D /* Headers */ = {
                isa = PBXHeadersBuildPhase;
                buildActionMask = 2147483647;
                files = (
                    4102E02227E0F84800A6AD9D /* hello.hpp in Headers */,
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
            4102E03527E1027F00A6AD9D /* Headers */ = {
                isa = PBXHeadersBuildPhase;
                buildActionMask = 2147483647;
                files = (
                    4102E03627E1027F00A6AD9D /* hello.hpp in Headers */,
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
    /* End PBXHeadersBuildPhase section */

    /* Begin PBXNativeTarget section */
            4102E01727E0F83900A6AD9D /* hello-dynamic */ = {
                isa = PBXNativeTarget;
                buildConfigurationList = 4102E01C27E0F83900A6AD9D /* Build configuration list for PBXNativeTarget "hello-dynamic" */;
                buildPhases = (
                    4102E01427E0F83900A6AD9D /* Headers */,
                    4102E01527E0F83900A6AD9D /* Sources */,
                    4102E01627E0F83900A6AD9D /* Frameworks */,
                );
                buildRules = (
                );
                dependencies = (
                );
                name = "hello-dynamic";
                productName = HelloLibrary;
                productReference = 4102E01827E0F83900A6AD9D /* libhello.dylib */;
                productType = "com.apple.product-type.library.static";
            };
            4102E03427E1027F00A6AD9D /* hello-static */ = {
                isa = PBXNativeTarget;
                buildConfigurationList = 4102E03A27E1027F00A6AD9D /* Build configuration list for PBXNativeTarget "hello-static" */;
                buildPhases = (
                    4102E03527E1027F00A6AD9D /* Headers */,
                    4102E03727E1027F00A6AD9D /* Sources */,
                    4102E03927E1027F00A6AD9D /* Frameworks */,
                );
                buildRules = (
                );
                dependencies = (
                );
                name = "hello-static";
                productName = HelloLibrary;
                productReference = 4102E03D27E1027F00A6AD9D /* libhello.a */;
                productType = "com.apple.product-type.library.static";
            };
    /* End PBXNativeTarget section */

    /* Begin PBXProject section */
            4102E01027E0F83900A6AD9D /* Project object */ = {
                isa = PBXProject;
                attributes = {
                    BuildIndependentTargetsInParallel = 1;
                    LastUpgradeCheck = 1320;
                    TargetAttributes = {
                        4102E01727E0F83900A6AD9D = {
                            CreatedOnToolsVersion = 13.2.1;
                        };
                    };
                };
                buildConfigurationList = 4102E01327E0F83900A6AD9D /* Build configuration list for PBXProject "HelloLibrary" */;
                compatibilityVersion = "Xcode 13.0";
                developmentRegion = en;
                hasScannedForEncodings = 0;
                knownRegions = (
                    en,
                    Base,
                );
                mainGroup = 4102E00F27E0F83900A6AD9D;
                productRefGroup = 4102E01927E0F83900A6AD9D /* Products */;
                projectDirPath = "";
                projectRoot = "";
                targets = (
                    4102E01727E0F83900A6AD9D /* hello-dynamic */,
                    4102E03427E1027F00A6AD9D /* hello-static */,
                );
            };
    /* End PBXProject section */

    /* Begin PBXSourcesBuildPhase section */
            4102E01527E0F83900A6AD9D /* Sources */ = {
                isa = PBXSourcesBuildPhase;
                buildActionMask = 2147483647;
                files = (
                    4102E02127E0F84800A6AD9D /* hello.cpp in Sources */,
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
            4102E03727E1027F00A6AD9D /* Sources */ = {
                isa = PBXSourcesBuildPhase;
                buildActionMask = 2147483647;
                files = (
                    4102E03827E1027F00A6AD9D /* hello.cpp in Sources */,
                );
                runOnlyForDeploymentPostprocessing = 0;
            };
    /* End PBXSourcesBuildPhase section */

    /* Begin XCBuildConfiguration section */
            4102E01A27E0F83900A6AD9D /* Debug */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 4102E03E27E1CEB000A6AD9D /* conan_config.xcconfig */;
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
                    DEPLOYMENT_LOCATION = NO;
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
                    MACOSX_DEPLOYMENT_TARGET = 12.1;
                    MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
                    MTL_FAST_MATH = YES;
                    ONLY_ACTIVE_ARCH = YES;
                    SDKROOT = macosx;
                };
                name = Debug;
            };
            4102E01B27E0F83900A6AD9D /* Release */ = {
                isa = XCBuildConfiguration;
                baseConfigurationReference = 4102E03E27E1CEB000A6AD9D /* conan_config.xcconfig */;
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
                    DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
                    DEPLOYMENT_LOCATION = NO;
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
                    MACOSX_DEPLOYMENT_TARGET = 12.1;
                    MTL_ENABLE_DEBUG_INFO = NO;
                    MTL_FAST_MATH = YES;
                    SDKROOT = macosx;
                };
                name = Release;
            };
            4102E01D27E0F83900A6AD9D /* Debug */ = {
                isa = XCBuildConfiguration;
                buildSettings = {
                    CODE_SIGN_STYLE = Automatic;
                    DEBUG_INFORMATION_FORMAT = dwarf;
                    EXECUTABLE_EXTENSION = dylib;
                    EXECUTABLE_PREFIX = lib;
                    MACH_O_TYPE = mh_dylib;
                    PRODUCT_NAME = hello;
                    SKIP_INSTALL = YES;
                };
                name = Debug;
            };
            4102E01E27E0F83900A6AD9D /* Release */ = {
                isa = XCBuildConfiguration;
                buildSettings = {
                    CODE_SIGN_STYLE = Automatic;
                    DEBUG_INFORMATION_FORMAT = dwarf;
                    EXECUTABLE_EXTENSION = dylib;
                    EXECUTABLE_PREFIX = lib;
                    MACH_O_TYPE = mh_dylib;
                    PRODUCT_NAME = hello;
                    SKIP_INSTALL = YES;
                };
                name = Release;
            };
            4102E03B27E1027F00A6AD9D /* Debug */ = {
                isa = XCBuildConfiguration;
                buildSettings = {
                    CODE_SIGN_STYLE = Automatic;
                    DEBUG_INFORMATION_FORMAT = dwarf;
                    EXECUTABLE_EXTENSION = a;
                    EXECUTABLE_PREFIX = lib;
                    MACH_O_TYPE = staticlib;
                    PRODUCT_NAME = hello;
                    SKIP_INSTALL = YES;
                };
                name = Debug;
            };
            4102E03C27E1027F00A6AD9D /* Release */ = {
                isa = XCBuildConfiguration;
                buildSettings = {
                    CODE_SIGN_STYLE = Automatic;
                    DEBUG_INFORMATION_FORMAT = dwarf;
                    EXECUTABLE_EXTENSION = a;
                    EXECUTABLE_PREFIX = lib;
                    MACH_O_TYPE = staticlib;
                    PRODUCT_NAME = hello;
                    SKIP_INSTALL = YES;
                };
                name = Release;
            };
    /* End XCBuildConfiguration section */

    /* Begin XCConfigurationList section */
            4102E01327E0F83900A6AD9D /* Build configuration list for PBXProject "HelloLibrary" */ = {
                isa = XCConfigurationList;
                buildConfigurations = (
                    4102E01A27E0F83900A6AD9D /* Debug */,
                    4102E01B27E0F83900A6AD9D /* Release */,
                );
                defaultConfigurationIsVisible = 0;
                defaultConfigurationName = Release;
            };
            4102E01C27E0F83900A6AD9D /* Build configuration list for PBXNativeTarget "hello-dynamic" */ = {
                isa = XCConfigurationList;
                buildConfigurations = (
                    4102E01D27E0F83900A6AD9D /* Debug */,
                    4102E01E27E0F83900A6AD9D /* Release */,
                );
                defaultConfigurationIsVisible = 0;
                defaultConfigurationName = Release;
            };
            4102E03A27E1027F00A6AD9D /* Build configuration list for PBXNativeTarget "hello-static" */ = {
                isa = XCConfigurationList;
                buildConfigurations = (
                    4102E03B27E1027F00A6AD9D /* Debug */,
                    4102E03C27E1027F00A6AD9D /* Release */,
                );
                defaultConfigurationIsVisible = 0;
                defaultConfigurationName = Release;
            };
    /* End XCConfigurationList section */
        };
        rootObject = 4102E01027E0F83900A6AD9D /* Project object */;
    }
    """)

hello_cpp = textwrap.dedent("""
    #include "hello.hpp"
    #include <iostream>

    void hellofunction(){
        #ifndef DEBUG
        std::cout << "Hello Release!" << std::endl;
        #else
        std::cout << "Hello Debug!" << std::endl;
        #endif
    }
    """)

hello_hpp = textwrap.dedent("""
    #ifndef hello_hpp
    #define hello_hpp

    void hellofunction();

    #endif /* hello_hpp */
    """)

test = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout
    from conan.tools.build import cross_building


    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
        # (it will be defined in Conan 2.0)
        generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv", "VirtualRunEnv"
        apply_env = False
        test_type = "explicit"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def layout(self):
            cmake_layout(self)

        def test(self):
            if not cross_building(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "example")
                self.run(cmd, env="conanrun")
                if self.options.shared:
                    self.run("otool -l {}".format(os.path.join(self.cpp.build.bindirs[0], "example")))
                else:
                    self.run("nm {}".format(os.path.join(self.cpp.build.bindirs[0], "example")))
    """)

cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(PackageTest CXX)

    find_package(hello CONFIG REQUIRED)

    add_executable(example src/example.cpp)
    target_link_libraries(example hello::hello)
    """)

test_src = textwrap.dedent("""
    #include "hello.hpp"

    int main() {
        hellofunction();
    }
    """)

conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.apple import XcodeBuild
    from conan.tools.files import copy

    class HelloLib(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        generators = "XcodeToolchain"
        exports_sources = "HelloLibrary.xcodeproj/*", "src/*"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def build(self):
            xcode = XcodeBuild(self)
            if self.options.shared:
                xcode.build("HelloLibrary.xcodeproj", target="hello-dynamic")
            else:
                xcode.build("HelloLibrary.xcodeproj", target="hello-static")

        def package(self):
            copy(self, "*/libhello*", src=self.build_folder, dst=os.path.join(self.package_folder, "lib"), keep_path=False)
            copy(self, "*/*.hpp", src=self.build_folder, dst=os.path.join(self.package_folder, "include"), keep_path=False)

        def package_info(self):
            self.cpp_info.libs = ["hello"]
    """)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
def test_shared_static_targets():
    """
    The pbxproj has defined two targets, one for static and one for dynamic libraries, in the
    XcodeBuild build helper we pass the target we want to build depending on the shared option
    """
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "src/hello.cpp": hello_cpp,
                 "src/hello.hpp": hello_hpp,
                 "HelloLibrary.xcodeproj/project.pbxproj": pbxproj,
                 "test_package/conanfile.py": test,
                 "test_package/src/example.cpp": test_src,
                 "test_package/CMakeLists.txt": cmakelists})
    client.run("create . -o *:shared=True -tf None")
    assert "Packaged 1 '.dylib' file: libhello.dylib" in client.out
    client.run("test test_package hello/1.0@ -o *:shared=True")
    assert "/build/Release/libhello.dylib" in client.out

    client.run("create . -tf None")
    assert "Packaged 1 '.a' file: libhello.a" in client.out
    client.run("test test_package hello/1.0@")
    # check the symbol hellofunction in in the executable
    assert "hellofunction" in client.out
