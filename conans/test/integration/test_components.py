import textwrap

from conans.test.assets.genconanfile import GenConanfile
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


def test_components_not_required():
    """
    Allow requiring and building against one component, but not propagating it
    https://github.com/conan-io/conan/issues/12965
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestcycleConan(ConanFile):
            name = "wayland"
            version = "1.0"
            requires = "expat/1.0"

            def package_info(self):
                self.cpp_info.components["wayland-scanner"].libdirs = []
        """)
    c.save({"expat/conanfile.py": GenConanfile("expat", "1.0"),
            "wayland/conanfile.py": conanfile})
    c.run("create expat")
    c.run("create wayland")
    assert "wayland/1.0: Created package" in c.out
