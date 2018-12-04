import os
import shutil
import unittest
from collections import namedtuple

from conans.client.tools import chdir
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestServer, TestClient
from conans.util.files import save, load
from conans.client.cmd.export import _replace_scm_data_in_conanfile
from conans.client.loader import _parse_conanfile
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
        _parse_conanfile(conan_file_path=self.conanfile_path)  # Check that the resulting file is valid python code.

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


class SCMUpload(unittest.TestCase):

    def scm_sources_test(self):
        """ Test conan_sources.tgz is deleted in server when removing 'exports_sources' and using
        'scm'"""
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "test"
    version = "1.0"
"""
        exports_sources = """
    exports_sources = "include/*"
"""
        servers = {"upload_repo": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                             users={"lasote": "mypass"})}
        client = TestClient(servers=servers, users={"upload_repo": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile + exports_sources, "include/file": "content"})
        client.run("create . danimtb/testing")
        client.run("upload test/1.0@danimtb/testing -r upload_repo")
        self.assertIn("Uploading conan_sources.tgz", client.out)
        conan_ref = ConanFileReference("test", "1.0", "danimtb", "testing")
        export_sources_path = os.path.join(servers["upload_repo"].paths.export(conan_ref),
                                           "conan_sources.tgz")
        self.assertTrue(os.path.exists(export_sources_path))

        scm = """
    scm = {"type": "git",
           "url": "auto",
           "revision": "auto"}
"""
        client.save({"conanfile.py": conanfile + scm})
        with chdir(client.current_folder):
            client.runner("git init")
            client.runner('git config user.email "you@example.com"')
            client.runner('git config user.name "Your Name"')
            client.runner("git remote add origin https://github.com/fake/fake.git")
            client.runner("git add .")
            client.runner("git commit -m \"initial commit\"")
        client.run("create . danimtb/testing")
        self.assertIn("Repo origin deduced by 'auto': https://github.com/fake/fake.git", client.out)
        client.run("upload test/1.0@danimtb/testing -r upload_repo")
        self.assertNotIn("Uploading conan_sources.tgz", client.out)
        export_sources_path = os.path.join(servers["upload_repo"].paths.export(conan_ref),
                                           "conan_sources.tgz")
        self.assertFalse(os.path.exists(export_sources_path))
