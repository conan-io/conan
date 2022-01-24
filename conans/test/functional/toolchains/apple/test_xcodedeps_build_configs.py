import os
import platform
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def create_xcode_project(client, project_name, source):
    pbxproj = textwrap.dedent("""
        // !$*UTF8*$!
        {{
            archiveVersion = 1;
            classes = {{
            }};
            objectVersion = 55;
            objects = {{

        /* Begin PBXBuildFile section */
                07879B4027219EE500B6FB51 /* main.cpp in Sources */ = {{isa = PBXBuildFile; fileRef = 07879B3F27219EE500B6FB51 /* main.cpp */; }};
        /* End PBXBuildFile section */

        /* Begin PBXCopyFilesBuildPhase section */
                07879B3A27219EE500B6FB51 /* CopyFiles */ = {{
                    isa = PBXCopyFilesBuildPhase;
                    buildActionMask = 2147483647;
                    dstPath = /usr/share/man/man1/;
                    dstSubfolderSpec = 0;
                    files = (
                    );
                    runOnlyForDeploymentPostprocessing = 1;
                }};
        /* End PBXCopyFilesBuildPhase section */

        /* Begin PBXFileReference section */
                07879B3C27219EE500B6FB51 /* {project_name} */ = {{isa = PBXFileReference; explicitFileType = "compiled.mach-o.executable"; includeInIndex = 0; path = {project_name}; sourceTree = BUILT_PRODUCTS_DIR; }};
                07879B3F27219EE500B6FB51 /* main.cpp */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.cpp.cpp; path = main.cpp; sourceTree = "<group>"; }};
        /* End PBXFileReference section */

        /* Begin PBXFrameworksBuildPhase section */
                07879B3927219EE500B6FB51 /* Frameworks */ = {{
                    isa = PBXFrameworksBuildPhase;
                    buildActionMask = 2147483647;
                    files = (
                    );
                    runOnlyForDeploymentPostprocessing = 0;
                }};
        /* End PBXFrameworksBuildPhase section */

        /* Begin PBXGroup section */
                07879B3327219EE500B6FB51 = {{
                    isa = PBXGroup;
                    children = (
                        07879B3E27219EE500B6FB51 /* {project_name} */,
                        07879B3D27219EE500B6FB51 /* Products */,
                    );
                    sourceTree = "<group>";
                }};
                07879B3D27219EE500B6FB51 /* Products */ = {{
                    isa = PBXGroup;
                    children = (
                        07879B3C27219EE500B6FB51 /* {project_name} */,
                    );
                    name = Products;
                    sourceTree = "<group>";
                }};
                07879B3E27219EE500B6FB51 /* {project_name} */ = {{
                    isa = PBXGroup;
                    children = (
                        07879B3F27219EE500B6FB51 /* main.cpp */,
                    );
                    path = {project_name};
                    sourceTree = "<group>";
                }};
        /* End PBXGroup section */

        /* Begin PBXNativeTarget section */
                07879B3B27219EE500B6FB51 /* {project_name} */ = {{
                    isa = PBXNativeTarget;
                    buildConfigurationList = 07879B4327219EE500B6FB51 /* Build configuration list for PBXNativeTarget "{project_name}" */;
                    buildPhases = (
                        07879B3827219EE500B6FB51 /* Sources */,
                        07879B3927219EE500B6FB51 /* Frameworks */,
                        07879B3A27219EE500B6FB51 /* CopyFiles */,
                    );
                    buildRules = (
                    );
                    dependencies = (
                    );
                    name = {project_name};
                    productName = {project_name};
                    productReference = 07879B3C27219EE500B6FB51 /* {project_name} */;
                    productType = "com.apple.product-type.tool";
                }};
        /* End PBXNativeTarget section */

        /* Begin PBXProject section */
                07879B3427219EE500B6FB51 /* Project object */ = {{
                    isa = PBXProject;
                    attributes = {{
                        BuildIndependentTargetsInParallel = 1;
                        LastUpgradeCheck = 1300;
                        TargetAttributes = {{
                            07879B3B27219EE500B6FB51 = {{
                                CreatedOnToolsVersion = 13.0;
                            }};
                        }};
                    }};
                    buildConfigurationList = 07879B3727219EE500B6FB51 /* Build configuration list for PBXProject "{project_name}" */;
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
                        07879B3B27219EE500B6FB51 /* {project_name} */,
                    );
                }};
        /* End PBXProject section */

        /* Begin PBXSourcesBuildPhase section */
                07879B3827219EE500B6FB51 /* Sources */ = {{
                    isa = PBXSourcesBuildPhase;
                    buildActionMask = 2147483647;
                    files = (
                        07879B4027219EE500B6FB51 /* main.cpp in Sources */,
                    );
                    runOnlyForDeploymentPostprocessing = 0;
                }};
        /* End PBXSourcesBuildPhase section */

        /* Begin XCBuildConfiguration section */
                07879B4127219EE500B6FB51 /* Debug */ = {{
                    isa = XCBuildConfiguration;
                    buildSettings = {{
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
                    }};
                    name = Debug;
                }};
                07879B4227219EE500B6FB51 /* Release */ = {{
                    isa = XCBuildConfiguration;
                    buildSettings = {{
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
                    }};
                    name = Release;
                }};
                07879B4427219EE500B6FB51 /* Debug */ = {{
                    isa = XCBuildConfiguration;
                    buildSettings = {{
                        CODE_SIGN_STYLE = Automatic;
                        PRODUCT_NAME = "$(TARGET_NAME)";
                    }};
                    name = Debug;
                }};
                07879B4527219EE500B6FB51 /* Release */ = {{
                    isa = XCBuildConfiguration;
                    buildSettings = {{
                        CODE_SIGN_STYLE = Automatic;
                        PRODUCT_NAME = "$(TARGET_NAME)";
                    }};
                    name = Release;
                }};
        /* End XCBuildConfiguration section */

        /* Begin XCConfigurationList section */
                07879B3727219EE500B6FB51 /* Build configuration list for PBXProject "{project_name}" */ = {{
                    isa = XCConfigurationList;
                    buildConfigurations = (
                        07879B4127219EE500B6FB51 /* Debug */,
                        07879B4227219EE500B6FB51 /* Release */,
                    );
                    defaultConfigurationIsVisible = 0;
                    defaultConfigurationName = Release;
                }};
                07879B4327219EE500B6FB51 /* Build configuration list for PBXNativeTarget "{project_name}" */ = {{
                    isa = XCConfigurationList;
                    buildConfigurations = (
                        07879B4427219EE500B6FB51 /* Debug */,
                        07879B4527219EE500B6FB51 /* Release */,
                    );
                    defaultConfigurationIsVisible = 0;
                    defaultConfigurationName = Release;
                }};
        /* End XCConfigurationList section */
            }};
            rootObject = 07879B3427219EE500B6FB51 /* Project object */;
        }}
        """)

    client.save({
        "{}.xcodeproj/project.pbxproj".format(project_name): pbxproj.format(
            project_name=project_name),
        "{}/main.cpp".format(project_name): source
    })


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake()
def test_xcodedeps_build_configurations():
    client = TestClient(path_with_spaces=False)

    client.run("new hello/0.1 -m=cmake_lib")
    client.run("export .")

    client.run("new bye/0.1 -m=cmake_lib")
    client.run("export .")

    main = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"
        #include "bye.h"
        int main(int argc, char *argv[]) {
            hello();
            bye();
            #ifndef DEBUG
            std::cout << "App Release!" << std::endl;
            #else
            std::cout << "App Debug!" << std::endl;
            #endif
        }
        """)

    project_name = "app"
    client.save({"conanfile.txt": "[requires]\nhello/0.1\nbye/0.1\n"}, clean_first=True)
    create_xcode_project(client, project_name, main)

    for config in ["Release", "Debug"]:
        client.run(
            "install . -s build_type={} -s arch=x86_64 --build=missing -g XcodeDeps".format(config))

    for config in ["Release", "Debug"]:
        client.run_command("xcodebuild -project {}.xcodeproj -xcconfig conandeps.xcconfig "
                           "-configuration {} -arch x86_64".format(project_name, config))
        client.run_command("./build/{}/{}".format(config, project_name))
        assert "App {}!".format(config) in client.out
        assert "hello/0.1: Hello World {}!".format(config).format(config) in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake()
def test_frameworks():
    client = TestClient(path_with_spaces=False)

    client.save({"hello.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                           .with_package_info(cpp_info={"frameworks":
                                                                        ['CoreFoundation']},
                                                              env_info={})})
    client.run("export hello.py hello/0.1@")

    main = textwrap.dedent("""
        #include <CoreFoundation/CoreFoundation.h>
        int main(int argc, char *argv[]) {
            CFShow(CFSTR("Hello!"));
        }
        """)

    project_name = "app"
    client.save({"conanfile.txt": "[requires]\nhello/0.1\n"}, clean_first=True)
    create_xcode_project(client, project_name, main)

    client.run("install . -s build_type=Release -s arch=x86_64 --build=missing -g XcodeDeps")

    client.run_command("xcodebuild -project {}.xcodeproj -xcconfig conandeps.xcconfig "
                       "-configuration Release -arch x86_64".format(project_name))
    client.run_command("./build/Release/{}".format(project_name))
    assert "Hello!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_xcodedeps_dashes_names_and_arch():
    # https://github.com/conan-io/conan/issues/9949
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.py": GenConanfile().with_name("hello-dashes").with_version("0.1")})
    client.run("export .")
    client.save({"conanfile.txt": "[requires]\nhello-dashes/0.1\n"}, clean_first=True)
    main = "int main(int argc, char *argv[]) { return 0; }"
    create_xcode_project(client, "app", main)
    client.run("install . -s arch=armv8 --build=missing -g XcodeDeps")
    assert os.path.exists(os.path.join(client.current_folder,
                                       "conan_hello_dashes_vars_release_arm64.xcconfig"))
    client.run_command("xcodebuild -project app.xcodeproj -xcconfig conandeps.xcconfig -arch arm64")
