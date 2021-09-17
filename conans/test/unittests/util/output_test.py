# -*- coding: utf-8 -*-
import os
import platform
import unittest
import zipfile
from io import StringIO

from conans.client import tools
from conans.client.output import ConanOutput
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, redirect_output
from conans.util.files import load, save


class OutputTest(unittest.TestCase):

    def test_simple_output(self):
        captured_output = RedirectedTestOutput()
        with redirect_output(captured_output):
            output = ConanOutput()
            output.rewrite_line("This is a very long line that has to be truncated somewhere, "
                                "because it is so long it doesn't fit in the output terminal")
        self.assertIn("This is a very long line that ha ... esn't fit in the output terminal",
                      captured_output.getvalue())

    def test_error(self):
        client = TestClient()
        conanfile = """
# -*- coding: utf-8 -*-

from conans import ConanFile
from conans.errors import ConanException

class PkgConan(ConanFile):
    def source(self):
       self.output.info("TEXT ÑÜíóúéáàèòù абвгдежзийкл 做戏之说  ENDTEXT")
"""
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        client.run("source .")
        self.assertIn("TEXT", client.out)
        self.assertIn("ENDTEXT", client.out)

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
            tools.unzip(zip_path, output_dir, output=ConanOutput())

        output = captured_output.getvalue()
        self.assertRegex(output, "Unzipping [\d]+B")
        content = load(os.path.join(output_dir, "example.txt"))
        self.assertEqual(content, "Hello world!")

    def test_short_paths_unzip_output(self):
        if platform.system() != "Windows":
            return
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "src/"*40, "example.txt")
        save(file_path, "Hello world!")

        zip_path = os.path.join(tmp_dir, 'example.zip')
        zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                zipf.write(os.path.join(root, f), os.path.join("src/"*20, f))
        zipf.close()

        output_dir = os.path.join(tmp_dir, "dst/"*40, "output_dir")
        captured_output = RedirectedTestOutput()
        with redirect_output(captured_output):
            tools.unzip(zip_path, output_dir, output=ConanOutput())

        output = captured_output.getvalue()
        self.assertIn("ERROR: Error extract src/src", output)
