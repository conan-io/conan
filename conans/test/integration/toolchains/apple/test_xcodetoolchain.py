import platform

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_toolchain_files():
    client = TestClient()
    client.save({"conanfile.txt": "[generators]\nXcodeToolchain\n"})
    client.run("install . -s build_type=Release")
    client.run("install . -s build_type=Debug")
    toolchain_all = client.load("conantoolchain.xcconfig")
    toolchain_vars_release = client.load("conantoolchain_release_x86_64.xcconfig")
    toolchain_vars_debug = client.load("conantoolchain_debug_x86_64.xcconfig")
    conan_config = client.load("conan_config.xcconfig")
    assert '#include "conantoolchain.xcconfig"' in conan_config
    assert '#include "conantoolchain_release_x86_64.xcconfig"' in toolchain_all
    assert '#include "conantoolchain_debug_x86_64.xcconfig"' in toolchain_all
    assert 'CLANG_CXX_LIBRARY[config=Debug][arch=x86_64][sdk=*]=libc++' in toolchain_vars_debug
    assert 'CLANG_CXX_LIBRARY[config=Release][arch=x86_64][sdk=*]=libc++' in toolchain_vars_release
