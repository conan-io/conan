import platform
import re
import textwrap

import pytest

from conan.test.utils.tools import TestClient


def _get_filename(configuration, architecture, sdk_version):
    props = [("configuration", configuration),
             ("architecture", architecture),
             ("sdk version", sdk_version)]
    name = "".join("_{}".format(v) for _, v in props if v is not None and v)
    name = name.replace(".", "_").replace("-", "_")
    return name.lower()


def _condition(configuration, architecture, sdk_version):
    sdk = "macosx{}".format(sdk_version or "*")
    return "[config={}][arch={}][sdk={}]".format(configuration, architecture, sdk)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.parametrize("configuration, os_version, libcxx, cppstd, arch, sdk_version, clang_cppstd", [
    ("Release", "", "", "", "x86_64", "", ""),
    ("Debug", "", "", "", "armv8", "", ""),
    ("Release", "12.0", "libc++", "20", "x86_64", "", "c++20"),
    ("Debug", "12.0", "libc++", "20", "x86_64", "", "c++20"),
    ("Release", "12.0", "libc++", "20", "x86_64", "11.3", "c++20"),
    ("Release", "12.0", "libc++", "20", "x86_64", "", "c++20"),
])
def test_toolchain_files(configuration, os_version, cppstd, libcxx, arch, sdk_version, clang_cppstd):
    client = TestClient()
    client.save({"conanfile.txt": "[generators]\nXcodeToolchain\n"})
    cmd = "install . -s build_type={}".format(configuration)
    cmd = cmd + " -s os.version={}".format(os_version) if os_version else cmd
    cmd = cmd + " -s compiler.cppstd={}".format(cppstd) if cppstd else cmd
    cmd = cmd + " -s os.sdk_version={}".format(sdk_version) if sdk_version else cmd
    cmd = cmd + " -s arch={}".format(arch) if arch else cmd
    client.run(cmd)
    arch_name = "arm64" if arch == "armv8" else arch
    filename = _get_filename(configuration, arch_name, sdk_version)
    condition = _condition(configuration, arch, sdk_version)

    toolchain_all = client.load("conantoolchain.xcconfig")
    toolchain_vars = client.load("conantoolchain{}.xcconfig".format(filename))
    conan_config = client.load("conan_config.xcconfig")

    assert '#include "conantoolchain.xcconfig"' in conan_config
    assert '#include "conantoolchain{}.xcconfig"'.format(filename) in toolchain_all

    if libcxx:
        assert 'CLANG_CXX_LIBRARY{}={}'.format(condition, libcxx) in toolchain_vars
    if os_version:
        assert 'MACOSX_DEPLOYMENT_TARGET{}={}'.format(condition, os_version) in toolchain_vars
    if cppstd:
        assert 'CLANG_CXX_LANGUAGE_STANDARD{}={}'.format(condition, clang_cppstd) in toolchain_vars


def test_toolchain_flags():
    client = TestClient()
    client.save({"conanfile.txt": "[generators]\nXcodeToolchain\n"})
    cmd = "install . -c 'tools.build:cxxflags=[\"flag1\"]' " \
          "-c 'tools.build:defines=[\"MYDEFINITION\"]' " \
          "-c 'tools.build:cflags=[\"flag2\"]' " \
          "-c 'tools.build:sharedlinkflags=[\"flag3\"]' " \
          "-c 'tools.build:exelinkflags=[\"flag4\"]'"
    client.run(cmd)
    conan_global_flags = client.load("conan_global_flags.xcconfig")
    assert "GCC_PREPROCESSOR_DEFINITIONS = $(inherited) MYDEFINITION" in conan_global_flags
    assert "OTHER_CFLAGS = $(inherited) flag2" in conan_global_flags
    assert "OTHER_CPLUSPLUSFLAGS = $(inherited) flag1" in conan_global_flags
    assert "OTHER_LDFLAGS = $(inherited) flag3 flag4" in conan_global_flags
    conan_global_file = client.load("conan_config.xcconfig")
    assert '#include "conan_global_flags.xcconfig"' in conan_global_file


def test_flags_generated_if_only_defines():
    # https://github.com/conan-io/conan/issues/16422
    client = TestClient()
    client.save({"conanfile.txt": "[generators]\nXcodeToolchain\n"})
    client.run("install . -c 'tools.build:defines=[\"MYDEFINITION\"]'")
    conan_global_flags = client.load("conan_global_flags.xcconfig")
    assert "GCC_PREPROCESSOR_DEFINITIONS = $(inherited) MYDEFINITION" in conan_global_flags
    conan_global_file = client.load("conan_config.xcconfig")
    assert '#include "conan_global_flags.xcconfig"' in conan_global_file


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.parametrize("os_name, sdk, min_version, deployment_target_flag", [
    ("Macos", None, "11.0", "MACOSX_DEPLOYMENT_TARGET"),
    ("iOS", "iphoneos", "18.0", "IPHONEOS_DEPLOYMENT_TARGET"),
    ("tvOS", "appletvos", "18.4", "TVOS_DEPLOYMENT_TARGET"),
    ("watchOS", "watchos", "9.0", "WATCHOS_DEPLOYMENT_TARGET"),
    ("visionOS", "xros", "2.0", "XROS_DEPLOYMENT_TARGET"),
])
def test_xcodetoolchain_xcconfig_deplyment_target(os_name, sdk, min_version, deployment_target_flag):
    client = TestClient()

    conanfile = textwrap.dedent(f"""
        import os
        from conan import ConanFile
        from conan.tools.apple import XcodeToolchain
        from conan.tools.files import save
        class MyApplicationConan(ConanFile):
            name = "myapplication"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def generate(self):
                tc = XcodeToolchain(self)
                tc.generate()
                # Private access to get the generated xcconfig filename
                # It changes based on the settings, so this is the less fragile way to get it
                save(self, os.path.join(self.generators_folder, "name.txt"), tc._vars_xconfig_filename)
        """)

    client.save({"conanfile.py": conanfile})

    settings = f"-s os={os_name} -s os.version={min_version}"
    if sdk:
        settings += f" -s os.sdk={sdk}"

    client.run(f"install . -s build_type=Release {settings} --build=missing")

    xcconfig_name = client.load("name.txt").strip()
    xcconfig = client.load(xcconfig_name)
    match = re.search(f"^{deployment_target_flag}.+={min_version}$", xcconfig, re.MULTILINE)
    assert match is not None
