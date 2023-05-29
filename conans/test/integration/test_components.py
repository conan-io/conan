import json
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


def test_components_overrides():
    """
    overrides are not direct dependencies, and as such, they don't need to be mandatory
    to specify in the components requires

    https://github.com/conan-io/conan/issues/13922
    """
    c = TestClient()
    consumer = textwrap.dedent("""
        from conan import ConanFile

        class ConanRecipe(ConanFile):
            name = "app"
            version = "0.1"

            def requirements(self):
                self.requires("libffi/3.4.4", override=True)
                self.requires("glib/2.76.2")

            def package_info(self):
                self.cpp_info.requires = ["glib::glib"]
        """)
    c.save({"libffi/conanfile.py": GenConanfile("libffi"),
           "glib/conanfile.py": GenConanfile("glib", "2.76.2").with_requires("libffi/3.0"),
            "app/conanfile.py": consumer})
    c.run("create libffi --version=3.0")
    c.run("create libffi --version=3.4.4")
    c.run("create glib")
    # This used to crash, because override was not correctly excluded
    c.run("create app")
    assert "app/0.1: Created package" in c.out


def test_components_get_global_values():
    """ Defining global cpp_info.xxxx will automatically translate to all components
    defined after that
    """
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile

        class ConanRecipe(ConanFile):
            name = "pkg"
            version = "0.1"

            def package_info(self):
                self.cpp_info.includedirs = ["myinclude"]
                self.cpp_info.libdirs = ["mylib"]
                self.cpp_info.components["potato"].libs = ["potato"]
                self.cpp_info.components["tomato"].libs = ["tomato"]
        """)
    c.save({"conanfile.py": pkg})
    c.run("create .")
    c.run("install --requires=pkg/0.1 --format=json")
    graph = json.loads(c.stdout)
    pkg_cpp_info = graph["graph"]["nodes"]["1"]["cpp_info"]
    assert "myinclude" in pkg_cpp_info["potato"]["includedirs"][0]
    assert "myinclude" in pkg_cpp_info["tomato"]["includedirs"][0]
    assert "mylib" in pkg_cpp_info["potato"]["libdirs"][0]
    assert "mylib" in pkg_cpp_info["tomato"]["libdirs"][0]
    # The default "bin" from the global one is also defined
    assert "bin" in pkg_cpp_info["potato"]["bindirs"][0]
    assert "bin" in pkg_cpp_info["tomato"]["bindirs"][0]
