import textwrap

from conans.test.utils.tools import TestClient


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
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "ERROR: There is a dependency loop in 'self.cpp_info.components' requires:" in c.out
    assert "a requires c"
    assert "b requires a"
    assert "c rquires b"
