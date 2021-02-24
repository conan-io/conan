import os
import textwrap

from bottle import static_file, request

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save


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

    def test_load_save_mkdir(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.files import load, save, mkdir

            class Pkg(ConanFile):
                name = "mypkg"
                version = "1.0"
                def source(self):
                    mkdir(self, "myfolder")
                    save(self, "./myfolder/myfile", "some_content")
                    assert load(self, "./myfolder/myfile") == "some_content"
            """)

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")

    def test_download(self):
        http_server = StoppableThreadBottle()
        file_path = os.path.join(temp_folder(), "myfile.txt")
        save(file_path, "some content")

        @http_server.server.get("/myfile.txt")
        def get_file():
            return static_file(os.path.basename(file_path), os.path.dirname(file_path))

        http_server.run_server()

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.files import download

            class Pkg(ConanFile):
                name = "mypkg"
                version = "1.0"
                def source(self):
                    download(self,
                             "http://localhost:{}/myfile.txt",
                             "myfile.txt")
            """.format(http_server.port))

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        local_path = os.path.join(client.current_folder, "myfile.txt")
        assert os.path.exists(local_path)
