import os
import textwrap

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
            def layout(self):
                self.folders.build = "mybuild"
                self.folders.generators = "mybuild/generators"
                self.cpp.build.bindirs = ["bin"]

            def generate(self):
                f = os.path.join(self.build_bin_folder, "myfile.txt")
                save(self, f, "mycontent!!!")

            def build(self):
                f = os.path.join(self.build_bin_folder, "myfile.txt")
                c = load(self, f)
                self.output.info(c)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create . --name=pkg --version=1.0")
    assert "pkg/1.0: mycontent!!!" in c.out
    c.run("install .")
    assert os.path.exists(os.path.join(c.current_folder, "mybuild", "bin", "myfile.txt"))
