import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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


def test_generate_build_folder_test_package():
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
                self.output.info(f"build_folder in test_package: {bool(self.build_folder)}")

            def test(self):
                pass
        """)

    c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
            "test_package/conanfile.py": conanfile})
    c.run("create .")
    assert f"build_folder in test_package: True" in c.out


class TestCustomTestPackage:
    def test_custom_test_package(self):
        c = TestClient(light=True)
        conanfile = GenConanfile("pkg", "0.1").with_class_attribute('test_package_folder="mytest"')
        c.save({"conanfile.py": conanfile,
                "mytest/conanfile.py": GenConanfile().with_test("self.output.info('MYTEST!')"),
                "mytest2/conanfile.py": GenConanfile().with_test("self.output.info('MYTEST2!')")})
        c.run("create .")
        assert "MYTEST!" in c.out
        c.run("create . -tf=mytest2")
        assert "MYTEST2!" in c.out

    def test_custom_test_package_subfolder(self):
        c = TestClient(light=True)
        conanfile = GenConanfile("pkg", "0.1").with_class_attribute('test_package_folder="my/test"')
        c.save({"pkg/conanfile.py": conanfile,
                "pkg/my/test/conanfile.py": GenConanfile().with_test("self.output.info('MYTEST!')")})
        c.run("create pkg")
        assert "MYTEST!" in c.out

    def test_custom_test_package_sibling(self):
        c = TestClient(light=True)
        conanfile = GenConanfile("pkg", "0.1").with_class_attribute(
            'test_package_folder="../my/test"')
        c.save({"pkg/conan/conanfile.py": conanfile,
                "pkg/my/test/conanfile.py": GenConanfile().with_test("self.output.info('MYTEST!')")})
        c.run("create pkg/conan")
        assert "MYTEST!" in c.out
