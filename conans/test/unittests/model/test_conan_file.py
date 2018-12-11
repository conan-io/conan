# coding=utf-8

import os
import shutil
import tempfile
import textwrap
import unittest
import uuid

from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import ConanFileLoader, ProcessedProfile
from conans.client.tools import save
from conans.model.conan_file import is_alias_conanfile


class IsAliasConanfileTest(unittest.TestCase):
    conanfile_base = textwrap.dedent("""\
        from conans import ConanFile
        
        class A(ConanFile):
            {placeholder}
        """)
    conanfile_alias = conanfile_base.format(placeholder='alias = "whatever"')
    conanfile_not_alias = conanfile_base.format(placeholder='pass')

    def run(self, *args, **kwargs):
        self.tmp_folder = tempfile.mkdtemp()
        try:
            super(IsAliasConanfileTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(self.tmp_folder)

    def _load_conanfile(self, content):
        file_path = os.path.join(self.tmp_folder, str(uuid.uuid4()) + ".py")
        save(file_path, content)
        loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))
        return loader.load_conanfile(file_path, None, ProcessedProfile())

    def test_alias(self):
        conanfile = self._load_conanfile(content=self.conanfile_alias)
        self.assertTrue(is_alias_conanfile(conanfile))

    def test_not_alias(self):
        conanfile = self._load_conanfile(content=self.conanfile_not_alias)
        self.assertFalse(is_alias_conanfile(conanfile))

    def test_not_conanfile(self):
        thing = ConanPythonRequire(None, None)
        self.assertRaises(AssertionError, is_alias_conanfile, thing)
