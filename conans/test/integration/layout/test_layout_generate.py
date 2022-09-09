import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_layout_generate():
    """ Trying to leverage the layout knowledge at generate() time and put some files
    in the bindirs folders where executables will be built, like some dll from other
    dependencies.
    https://github.com/conan-io/conan/issues/12003
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save, load
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            def layout(self):
                self.folders.build = "mybuild"
                self.folders.generators = "mybuild/generators"
                self.cpp.build.bindirs = ["bin"]
                self.cpp.build.libdirs = ["lib"]
                self.cpp.build.includedirs = ["include"]
            def generate(self):
                f = os.path.join(self.build_folder, self.cpp.build.bindir, "myfile.txt")
                save(self, f, "mybin!!!")
                f = os.path.join(self.build_folder, self.cpp.build.libdir, "myfile.txt")
                save(self, f, "mylib!!!")
                f = os.path.join(self.build_folder, self.cpp.build.includedir, "myfile.txt")
                save(self, f, "myinclude!!!")

            def build(self):
                self.output.info(load(self, os.path.join(self.cpp.build.libdir, "myfile.txt")))
                self.output.info(load(self, os.path.join(self.cpp.build.bindir, "myfile.txt")))
                self.output.info(load(self, os.path.join(self.cpp.build.includedir, "myfile.txt")))
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create . ")
    assert "pkg/1.0: mybin!!!" in c.out
    assert "pkg/1.0: mylib!!!" in c.out
    assert "pkg/1.0: myinclude!!!" in c.out
    c.run("install .")
    assert os.path.exists(os.path.join(c.current_folder, "mybuild", "bin", "myfile.txt"))
    assert os.path.exists(os.path.join(c.current_folder, "mybuild", "lib", "myfile.txt"))
    assert os.path.exists(os.path.join(c.current_folder, "mybuild", "include", "myfile.txt"))


def test_generate_source_folder():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def layout(self):
                cmake_layout(self)

            def generate(self):
                self.output.info("PKG_CONFIG_PATH {}!".format(os.path.exists(self.source_folder)))
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install .")
    assert "PKG_CONFIG_PATH True!" in c.out


def test_generate_source_folder_test_package():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def layout(self):
                cmake_layout(self)

            def generate(self):
                self.output.info("PKG_CONFIG_PATH {}!".format(os.path.exists(self.source_folder)))

            def test(self):
                pass
        """)
    c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
            "test_package/conanfile.py": conanfile})
    c.run("create .")
    assert "PKG_CONFIG_PATH True!" in c.out
