import os
import textwrap

from bottle import static_file

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save
from conans.test.assets.genconanfile import GenConanfile


class TestConanToolFiles:

    def test_imports(self):
        conanfile = GenConanfile().with_import("from conan.tools.files import load, save, "
                                               "mkdir, download, get, ftp_download")
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

        profile = textwrap.dedent("""\
            [conf]
            tools.files.download:retry=1
            tools.files.download:retry_wait=0
            """)

        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conan.tools.files import download

            class Pkg(ConanFile):
                name = "mypkg"
                version = "1.0"
                def source(self):
                    download(self, "http://localhost:{}/myfile.txt", "myfile.txt")
                    assert os.path.exists("myfile.txt")
            """.format(http_server.port))

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.save({"profile": profile})
        client.run("create . -pr=profile")
