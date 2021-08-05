import os
import textwrap

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


def test_removed_folder():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import save
        from conans import ConanFile

        class Recipe(ConanFile):
            def post_package(self):
                file_path = os.path.join(self.post_package_folder, "foo.txt")
                save(self, file_path, "bar")
        """)

    client.save({"conanfile.py": conanfile})
    client.run("create . foo/1.0@")
    ref = ConanFileReference.loads("foo/1.0")
    pref = client.get_latest_prev(ref)
    layout = client.get_latest_pkg_layout(pref)
    assert os.path.exists(os.path.join(layout.post_package(), "foo.txt"))
    client.run("remove foo/1.0@ -f")
    assert not os.path.exists(layout.post_package())

    # Create again the pockage
    client.run("create . foo/1.0@")

    # remove the method and create again
    conanfile = textwrap.dedent("""
            import os
            from conan.tools.files import save
            from conans import ConanFile

            class Recipe(ConanFile):
                def package(self):
                    file_path = os.path.join(self.package_folder, "foo_bar.txt")
                    save(self, file_path, "bar")
            """)
    client.save({"conanfile.py": conanfile})
    client.run("create . foo/1.0@")
    pref = client.get_latest_prev(ref)
    layout = client.get_latest_pkg_layout(pref)
    assert not os.path.exists(layout.post_package())
    assert os.path.exists(os.path.join(layout.package(), "foo_bar.txt"))


def test_post_package_method():
    client = TestClient()
    conanfile = textwrap.dedent("""
    import os
    from conan.tools.files import save
    from conans import ConanFile

    class Recipe(ConanFile):

        def build(self):
            save(self, "mylibrary.lib", "contents")

        def package(self):
            self.copy("mylibrary.lib", dst="lib")

        def post_package(self):
            file_path = os.path.join(self.post_package_folder, "lib", "mylibrary.lib")
            assert os.path.exists(file_path)
            with open(file_path, "w") as _f:
                _f.write("modified contents")

        def package_info(self):
            self.cpp_info.libs = ["mylibrary.lib"]

    """)

    client.save({"conanfile.py": conanfile})
    client.run("create . foo/1.0@")
    client.run("install foo/1.0@ -g CMakeDeps")
    asserted = False
    with open(os.path.join(client.current_folder, "foo-release-x86_64-data.cmake")) as _f:
        for _l in _f.readlines():
            if _l.startswith("set(foo_PACKAGE_FOLDER_RELEASE "):
                _tmp = _l.split('"')
                folder = _tmp[1]
                assert folder.endswith("install")
                with open(os.path.join(folder, "lib", "mylibrary.lib")) as _lib:
                    contents = _lib.read()
                    asserted = True
                    assert "modified contents" in contents

    assert asserted
