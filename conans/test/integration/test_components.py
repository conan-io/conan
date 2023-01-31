import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_components_cycles():
    """c -> b -> a -> c"""
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
    with pytest.raises(Exception) as exc:
        c.run("create .")
    out = str(exc.value)
    assert "ERROR: Error in generator 'CMakeDeps': error generating context for 'testcycle/1.0': " \
           "There is a dependency loop in 'self.cpp_info.components' requires:" in out
    assert "a requires c" in out
    assert "b requires a" in out
    assert "c requires b" in out


def test_components_cycle_complex():
    """
    Cycle: a -> b -> c -> d -> b
    Isolated j declaring its libs
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestcycleConan(ConanFile):
            name = "testcycle"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["a"].requires = ["b"]
                self.cpp_info.components["b"].requires = ["c"]
                self.cpp_info.components["c"].requires = ["d"]
                self.cpp_info.components["d"].requires = ["b"]  # cycle!
                self.cpp_info.components["j"].libs = ["libj"]
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
    with pytest.raises(Exception) as exc:
        c.run("create .")
    out = str(exc.value)
    assert "ERROR: Error in generator 'CMakeDeps': error generating context for 'testcycle/1.0': " \
           "There is a dependency loop in 'self.cpp_info.components' requires:" in out
    assert "a requires b" in out
    assert "b requires c" in out
    assert "c requires d" in out
    assert "d requires b" in out


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
