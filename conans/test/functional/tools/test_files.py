import textwrap

from conans.test.utils.tools import TestClient


class TestConanToolFiles:

    def test_imports(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.files import load, save, mkdir, download, get, ftp_download

            class Pkg(ConanFile):
                pass
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

    def test_old_imports(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import load, save, mkdir, download, get, ftp_download

            class Pkg(ConanFile):
                pass
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
