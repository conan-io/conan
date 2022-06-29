import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="The detection of cycles have been removed in 2.0, this test hangs")
def test_components_cycles():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestcycleConan(ConanFile):
            name = "testcycle"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["c"].requires = ["b"]
                self.cpp_info.components["b"].requires = ["a"]
                self.cpp_info.components["a"].requires = ["c"] # cycle!
        """)
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Test(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeDeps"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
            """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": test_conanfile})
    c.run("create .", assert_error=True)
    print(c.out)
    assert "ERROR: There is a dependency loop in 'self.cpp_info.components' requires:" in c.out
    assert "a requires c"
    assert "b requires a"
    assert "c rquires b"
