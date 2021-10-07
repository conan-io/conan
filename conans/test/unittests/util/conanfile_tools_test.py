import os
import stat
import sys
import unittest

from mock import Mock

from conans.client import tools
from conans.client.output import ConanOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import load, save
from conans.client.tools.files import replace_in_file, replace_path_in_file


base_conanfile = '''
from conans import ConanFile
from conans.tools import patch, replace_in_file
import os

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9.10"
'''


class ConanfileToolsTest(unittest.TestCase):

    def test_save_append(self):
        # https://github.com/conan-io/conan/issues/2841 (regression)
        client = TestClient()
        conanfile = """from conans import ConanFile
from conans.tools import save
class Pkg(ConanFile):
    def source(self):
        save("myfile.txt", "Hello", append=True)
"""
        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "World"})
        client.run("source .")
        self.assertEqual("WorldHello", client.load("myfile.txt"))

    def test_untar(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "example.txt")
        save(file_path, "Hello world!")
        tar_path = os.path.join(tmp_dir, "sample.tar")
        try:
            old_path = os.getcwd()
            os.chdir(tmp_dir)
            import tarfile
            tar = tarfile.open(tar_path, "w")
            tar.add("example.txt")
            tar.close()
        finally:
            os.chdir(old_path)
        output_dir = os.path.join(tmp_dir, "output_dir")
        tools.unzip(tar_path, output_dir, output=ConanOutput(stream=sys.stdout))
        content = load(os.path.join(output_dir, "example.txt"))
        self.assertEqual(content, "Hello world!")

    def test_replace_in_file(self):
        tmp_dir = temp_folder()
        text_file = os.path.join(tmp_dir, "text.txt")
        save(text_file, "ONE TWO THREE")
        replace_in_file(text_file, "ONE TWO THREE", "FOUR FIVE SIX", output=Mock())
        self.assertEqual(load(text_file), "FOUR FIVE SIX")

    def test_replace_in_file_readonly(self):
        tmp_dir = temp_folder()
        text_file = os.path.join(tmp_dir, "text.txt")
        save(text_file, "ONE TWO THREE")

        os.chmod(text_file,
                 os.stat(text_file).st_mode & ~(stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH))
        mode_before_replace = os.stat(text_file).st_mode

        replace_in_file(text_file, "ONE TWO THREE", "FOUR FIVE SIX", output=Mock())
        self.assertEqual(load(text_file), "FOUR FIVE SIX")

        self.assertEqual(os.stat(text_file).st_mode, mode_before_replace)

        replace_path_in_file(text_file, "FOUR FIVE SIX", "SEVEN EIGHT NINE", output=Mock())
        self.assertEqual(load(text_file), "SEVEN EIGHT NINE")

        self.assertEqual(os.stat(text_file).st_mode, mode_before_replace)
