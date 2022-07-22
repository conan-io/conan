import os
import re
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


def test_requires_components_new_syntax():
    """
    lib_a: has four components cmp1, cmp2, cmp3, cmp4
    lib_b --> uses libA cmp1 so cpp_info.requires = ["lib_a::cmp1"]
    lib_c --> uses libA cmp2 so cpp_info.requires = ["lib_a::cmp2"]
    consumer --> libB, libC
    """
    client = TestClient()
    lib_a = textwrap.dedent("""
        from conan import ConanFile
        class lib_aConan(ConanFile):
            name = "lib_a"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["cmp1"].includedirs = ["include"]
                self.cpp_info.components["cmp2"].includedirs = ["include"]
        """)

    lib_b = GenConanfile("lib_b", "1.0")

    client.save({'lib_a/conanfile.py': lib_a, 'lib_b/conanfile.py': lib_b})

    client.run("create lib_a")

    client.run("create lib_b")

    """
    Check that the generated lib_c files use lib_a::cmp1 and lib_b but not lib_a::cmp2
    The results must be equivalent to the declaration of
        def package_info(self):
            self.cpp_info.requires = ["lib_a::cmp1", "lib_b::lib_b"]
    in lib_c
    """

    lib_c = textwrap.dedent("""
        from conan import ConanFile
        class lib_cConan(ConanFile):
            name = "lib_c"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            {rest_of_file}
        """)

    new_syntax = """
    def requirements(self):
        self.requires("lib_a/1.0", components=["cmp1"])
        self.requires("lib_b/1.0")
    """

    old_syntax = """
    def requirements(self):
        self.requires("lib_a/1.0")
        self.requires("lib_b/1.0")
    def package_info(self):
        self.cpp_info.requires = ["lib_a::cmp1", "lib_b::lib_b"]
    """

    for generator in ["CMakeDeps", "XcodeDeps", "PkgConfigDeps", "MSBuildDeps"]:

        client.save({'lib_c/conanfile.py': lib_c.format(rest_of_file=new_syntax)},
                    clean_first=True)

        client.run("create lib_c")

        client.run(f"install --requires=lib_c/1.0 -g {generator} -of=output")

        generated_files = {}
        for _, _, files in os.walk(os.path.join(client.current_folder, "output")):
            for f in files:
                file_content = client.load(os.path.join(client.current_folder, "output", f))
                # remove info about cache folders
                file_content = re.sub(fr'(?s)(\.conan2{os.path.sep}p)(.*?)(p)', "", file_content)
                generated_files[f] = file_content

        client.save({'lib_c/conanfile.py': lib_c.format(rest_of_file=old_syntax)},
                    clean_first=True)

        client.run("create lib_c")

        client.run(f"install --requires=lib_c/1.0 -g {generator} -of=output")

        # the generated files with the old syntax should be exactly the same as the new one
        for _, _, files in os.walk(os.path.join(client.current_folder, "output")):
            for f in files:
                old_syntax_file = client.load(os.path.join(client.current_folder, "output", f))
                old_syntax_file = re.sub(fr'(?s)(\.conan2{os.path.sep}p)(.*?)(p)', "", old_syntax_file)
                assert generated_files[f] == old_syntax_file
