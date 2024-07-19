import os
import platform
import unittest
import zipfile

import pytest

from conan.tools.files import unzip
from conan.test.utils.mocks import RedirectedTestOutput, ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, redirect_output
from conans.util.files import load, save


class OutputTest(unittest.TestCase):

    def test_error(self):
        client = TestClient()
        conanfile = """
# -*- coding: utf-8 -*-

from conan import ConanFile
from conan.errors import ConanException

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
            unzip(ConanFileMock(), zip_path, output_dir)

        output = captured_output.getvalue()
        self.assertRegex(output, r"Unzipping [\d]+B")
        content = load(os.path.join(output_dir, "example.txt"))
        self.assertEqual(content, "Hello world!")

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires windows")
    def test_short_paths_unzip_output(self):
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
            unzip(ConanFileMock(), zip_path, output_dir)

        output = captured_output.getvalue()
        self.assertIn("ERROR: Error extract src/src", output)
