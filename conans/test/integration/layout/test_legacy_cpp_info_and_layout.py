import textwrap

import pytest

from conans.test.utils.tools import TestClient


# TODO: This test does not make sense for Conan v2. Please, remove/skip it in that case.
@pytest.mark.parametrize("declare_layout", [True, False])
def test_legacy_deps_cpp_info_deps_version_using_or_not_layout(declare_layout):
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class HelloConan(ConanFile):
        name = "hello"
        version = "1.0"
        {}
        def package_info(self):
            self.cpp_info.libs = ["hello"]
    """.format("def layout(self):pass" if declare_layout else ""))
    test_conanfile = textwrap.dedent("""
    from conan import ConanFile

    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"

        def build(self):
            self.output.info(self.deps_cpp_info["hello"].version)

        def test(self):
            pass
    """)
    client = TestClient()
    client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile})
    client.run("create .")
    assert "hello/1.0 (test package): 1.0" in client.out
