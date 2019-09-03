# coding=utf-8

import textwrap
import unittest

from parameterized import parameterized
from parameterized.parameterized import parameterized_class

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, create_local_git_repo
from conans.util.files import load


@parameterized_class([{"shallow": True}, {"shallow": False}, {"shallow": None}, {"shallow": "None"}])
class GitShallowTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.errors import ConanException
        from six import StringIO
        
        class Lib(ConanFile):
            scm = {{"type": "git", "url": "{url}", "revision": "{rev}", {shallow_attrib} }}
            
            def build(self):
                try:
                    mybuf = StringIO()
                    out = self.run("git describe --tags", output=mybuf)
                    self.output.info(">>> tags: {{}}".format(mybuf.getvalue()))
                except ConanException:
                    self.output.info(">>> describe-fails")
    """)

    ref = ConanFileReference.loads("name/version@user/channel")

    def _shallow_attrib_str(self):
        shallow_attrib_str = ""
        if self.shallow is not None:
            shallow_attrib_str = '"shallow": {}'.format(self.shallow)
        return shallow_attrib_str

    def test_export(self):
        # Check the shallow value is substituted with the proper value
        client = TestClient()
        files = {'conanfile.py': self.conanfile.format(shallow_attrib=self._shallow_attrib_str(),
                                                       url='auto', rev='auto')}
        url, _ = create_local_git_repo(files=files)

        client.run_command('git clone "{}" .'.format(url))

        client.run("export . {}".format(self.ref))
        content = load(client.cache.package_layout(self.ref).conanfile())
        if self.shallow in [None, True, "None"]:
            self.assertNotIn("shallow", content)
        else:
            self.assertIn('"shallow": False', content)

        client.run("inspect {} -a scm".format(self.ref))  # Check we get a loadable conanfile.py

    @parameterized.expand([("c6cc15fa2f4b576bd", False), ("0.22.1", True)])
    def test_remote_build(self, revision, shallow_works):
        # Shallow works only with branches or tags
        client = TestClient()
        client.save({'conanfile.py':
                         self.conanfile.format(shallow_attrib=self._shallow_attrib_str(),
                                               url="https://github.com/conan-io/conan.git",
                                               rev=revision)})

        client.run("create . {}".format(self.ref))

        if self.shallow in [None, True, "None"] and shallow_works:
            self.assertIn(">>> describe-fails", client.out)
        else:
            self.assertIn(">>> tags: 0.22.1", client.out)
