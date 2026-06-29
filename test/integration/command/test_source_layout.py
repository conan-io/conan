import textwrap

from conan.test.utils.tools import TestClient


class TestSourceLayout:
    """layout_source() is a profile-independent alternative to layout() for defining
    source folder, folders.root, and folders.subproject."""

    def test_source_layout_used_for_source_not_layout(self):
        # source_layout() sets folders for 'conan source'; layout() is used for install/create.
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import save

            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"

                def layout_source(self):
                    self.folders.source = "source_src"

                def layout(self):
                    self.folders.build = "mybuild"

                def source(self):
                    self.output.info(f"source_folder={self.source_folder}!!!")
                    save(self, "hello.cpp", "hello")

                def build(self):
                    self.output.info(f"build_folder={self.build_folder}!!!")
                    save(self, "hello.obj", "myobj")
        """)
        client = TestClient(light=True)
        client.save({"conanfile.py": conanfile})

        client.run("source .")
        # source_layout() must have been used: file lands in source_src/
        assert "source_src!!!" in client.out
        assert client.load("source_src/hello.cpp") == "hello"

        client.run("build")
        assert "mybuild!!!" in client.out
        assert client.load("mybuild/hello.obj") == "myobj"

        # layout() is still used during create (source_layout() runs for package_id computation too)
        client.run("create .")
        assert "source_src!!!" in client.out
        assert "mybuild!!!" in client.out

    def test_source_layout_root_and_subproject_paths(self):
        # folders.root and folders.subproject set in source_layout() shift the base paths.
        # conanfile.py lives in mylib/; root=".." goes up to workspace root, subproject="mylib"
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import save

            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"

                def layout_source(self):
                    self.folders.root = ".."
                    self.folders.subproject = "mylib"
                    self.folders.source = "mylib/src"

                def source(self):
                    save(self, "lib.cpp", "code")
        """)
        client = TestClient(light=True)
        client.save({"mylib/conanfile.py": conanfile})
        client.run("source mylib")
        # The saved file should be at workspace_root/mylib/src/lib.cpp
        assert client.load("mylib/src/lib.cpp") == "code"

    def test_source_layout_fallback_to_layout(self):
        # When source_layout() is absent, layout() is the fallback for 'conan source'.
        # Verifies the source folder value comes from layout() and files land in the right place.
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import save

            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"

                def layout(self):
                    self.folders.source = "layout_src"

                def source(self):
                    self.output.info(f"source_folder={self.source_folder}")
                    save(self, "file.cpp", "content")
        """)
        client = TestClient(light=True)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        assert "layout_src" in client.out
        assert client.load("layout_src/file.cpp") == "content"
