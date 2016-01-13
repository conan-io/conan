import unittest
import os
from conans.util.files import save, load
from conans.client.loader import ConanFileLoader
from conans.model.settings import Settings
from conans.model.options import OptionsValues
from conans.test.utils.test_files import temp_folder


class ConanfileToolsTest(unittest.TestCase):

    def test_replace_in_file(self):
        file_content = '''
from conans import ConanFile
from conans.tools import download, unzip, replace_in_file
import os

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9.10"
    settings = []

    def source(self):
        pass

    def build(self):
        replace_in_file("otherfile.txt", "ONE TWO THREE", "FOUR FIVE SIX")

'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.py")
        other_file = os.path.join(tmp_dir, "otherfile.txt")
        save(file_path, file_content)
        save(other_file, "ONE TWO THREE")
        loader = ConanFileLoader(None, Settings(), OptionsValues.loads(""))
        ret = loader.load_conan(file_path, None)
        curdir = os.path.abspath(os.curdir)
        os.chdir(tmp_dir)
        try:
            ret.build()
        finally:
            os.chdir(curdir)

        content = load(other_file)
        self.assertEquals(content, "FOUR FIVE SIX")
