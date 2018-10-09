
import os
import shutil
import unittest
from collections import namedtuple

from conans.util.files import save, load
from conans.client.cmd.export import _replace_scm_data_in_conanfile
from conans.client.loader import _parse_file
from conans.test.utils.test_files import temp_folder
from conans.model.scm import SCMData


class ReplaceSCMDataInConanfileTest(unittest.TestCase):
    conanfile = """
from conans import ConanFile

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {{"revision": "{revision}",
           "type": "git",
           "url": "{url}"}}
    
    {after_scm}

{after_recipe}
"""

    def run(self, *args, **kwargs):
        self.tmp_folder = temp_folder()
        self.conanfile_path = os.path.join(self.tmp_folder, 'conanfile.py')
        try:
            super(ReplaceSCMDataInConanfileTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(self.tmp_folder)

    def _do_actual_test(self, scm_data, after_scm, after_recipe):
        target_conanfile = self.conanfile.format(url=scm_data['url'],
                                                 revision=scm_data['revision'],
                                                 after_scm=after_scm,
                                                 after_recipe=after_recipe)
        save(self.conanfile_path, content=self.conanfile.format(url='auto', revision='auto',
                                                                after_scm=after_scm,
                                                                after_recipe=after_recipe))
        scm_data = SCMData(conanfile=namedtuple('_', 'scm')(scm=scm_data))
        _replace_scm_data_in_conanfile(self.conanfile_path, scm_data)
        self.assertEqual(load(self.conanfile_path), target_conanfile)
        _parse_file(self.conanfile_path)  # Check that the resulting file is valid python code.

    def test_conanfile_after_scm(self):
        scm_data = {'type': 'git',
                    'url': 'url_value',
                    'revision': 'revision_value'}
        after_scm = 'attrib = 23'
        after_recipe = ''
        self._do_actual_test(scm_data=scm_data, after_scm=after_scm, after_recipe=after_recipe)

    def test_conanfile_after_scm_and_recipe(self):
        scm_data = {'type': 'git',
                    'url': 'url_value',
                    'revision': 'revision_value'}
        after_scm = 'attrib = 23'
        after_recipe = 'another = 23'
        self._do_actual_test(scm_data=scm_data, after_scm=after_scm, after_recipe=after_recipe)

    def test_conanfile_after_recipe(self):
        scm_data = {'type': 'git',
                    'url': 'url_value',
                    'revision': 'revision_value'}
        after_scm = ''
        after_recipe = 'another = 23'
        self._do_actual_test(scm_data=scm_data, after_scm=after_scm, after_recipe=after_recipe)

    def test_conanfile_none(self):
        scm_data = {'type': 'git',
                    'url': 'url_value',
                    'revision': 'revision_value'}
        after_scm = ''
        after_recipe = ''
        self._do_actual_test(scm_data=scm_data, after_scm=after_scm, after_recipe=after_recipe)
