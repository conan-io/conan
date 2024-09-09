from parameterized import parameterized

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@parameterized.expand(["AutotoolsToolchain", "MesonToolchain", "BazelToolchain"])
def test_create_universal_binary(toolchain):
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type").with_generator(toolchain))
    client.save({"conanfile.py": conanfile})

    client.run('create . --name=foo --version=1.0 -s="arch=armv8|armv8.3|x86_64"',
               assert_error=True)
    assert f"Error in generator '{toolchain}': Universal binaries not supported by toolchain." in client.out
