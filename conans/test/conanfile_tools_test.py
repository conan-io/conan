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

    def test_patch_from_file(self):
        file_content = '''
from conans import ConanFile
from conans.tools import patch
import os

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9.10"
    settings = []

    def source(self):
        pass

    def build(self):
        patch(patch_file="file.patch")

'''
        patch_content = '''--- text.txt\t2016-01-25 17:57:11.452848309 +0100
+++ text_new.txt\t2016-01-25 17:57:28.839869950 +0100
@@ -1 +1 @@
-ONE TWO THREE
+ONE TWO FOUR'''

        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.py")
        text_file = os.path.join(tmp_dir, "text.txt")
        patch_file = os.path.join(tmp_dir, "file.patch")
        save(file_path, file_content)
        save(text_file, "ONE TWO THREE")
        save(patch_file, patch_content)
        loader = ConanFileLoader(None, Settings(), OptionsValues.loads(""))
        ret = loader.load_conan(file_path, None)
        curdir = os.path.abspath(os.curdir)
        os.chdir(tmp_dir)
        try:
            ret.build()
        finally:
            os.chdir(curdir)

        content = load(text_file)
        self.assertEquals(content, "ONE TWO FOUR")

    def test_patch_from_str(self):
        file_content = '''
from conans import ConanFile
from conans.tools import patch
import os

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9.10"
    settings = []

    def source(self):
        pass

    def build(self):
        patch_content = \'''--- text.txt\t2016-01-25 17:57:11.452848309 +0100
+++ text_new.txt\t2016-01-25 17:57:28.839869950 +0100
@@ -1 +1 @@
-ONE TWO THREE
+ONE TWO DOH!\'''
        patch(patch_string=patch_content)

'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.py")
        text_file = os.path.join(tmp_dir, "text.txt")
        save(file_path, file_content)
        save(text_file, "ONE TWO THREE")
        loader = ConanFileLoader(None, Settings(), OptionsValues.loads(""))
        ret = loader.load_conan(file_path, None)
        curdir = os.path.abspath(os.curdir)
        os.chdir(tmp_dir)
        try:
            ret.build()
        finally:
            os.chdir(curdir)

        content = load(text_file)
        self.assertEquals(content, "ONE TWO DOH!")
