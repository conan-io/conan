import os
import textwrap
import zipfile

from conan.tools.files import unzip
from conan.test.utils.mocks import RedirectedTestOutput, ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, redirect_output
from conan.internal.util.files import load, save


class TestOutput:

    def test_error(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class PkgConan(ConanFile):
                def source(self):
                   self.output.info("TEXT ÑÜíóúéáàèòù абвгдежзийкл 做戏之说  ENDTEXT")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        client.run("source .")
        assert "TEXT" in client.out
        assert "ENDTEXT" in client.out

    def test_unzip_output(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "example.txt")
        save(file_path, "Hello world!")

        zip_path = os.path.join(tmp_dir, 'example.zip')
        zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                zipf.write(os.path.join(root, f), f)
        zipf.close()

        output_dir = os.path.join(tmp_dir, "output_dir")
        captured_output = RedirectedTestOutput()
        with redirect_output(captured_output):
            unzip(ConanFileMock(), zip_path, output_dir)

        output = captured_output.getvalue()
        assert "Unzipping" in output
        content = load(os.path.join(output_dir, "example.txt"))
        assert content == "Hello world!"
