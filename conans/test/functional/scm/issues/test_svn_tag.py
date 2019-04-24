# coding=utf-8

import os
import textwrap

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import SVNLocalRepoTestCase, TestClient, \
    load


@attr('svn')
class SVNTaggedComponentTest(SVNLocalRepoTestCase):
    # Reproducing https://github.com/conan-io/conan/issues/5017

    def setUp(self):
        # Create a sample SVN repository
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools
            
            class Lib(ConanFile):
                scm = {"type": "svn", "url": "auto", "revision": "auto"}
        """)
        files = {'level0.txt': "level0",
                 'level1/level1.txt': "level1",
                 'level1/conanfile.py': conanfile,
                 'tags/sentinel': ""}
        self.project_url, rev = self.create_project(files=files)
        self.project_url = self.project_url.replace(" ", "%20")

        # Create a tag for 'level1' component
        t = TestClient()
        t.runner('svn copy {url}/level1 {url}/tags/level1-1.0'
                 ' -m "Release level1-1.0"'.format(url=self.project_url), cwd=t.current_folder)

    def test_auto_tag(self):
        t = TestClient()
        ref = ConanFileReference.loads("lib/version@issue/testing")

        # Clone the tag to local folder
        url = os.path.join(self.project_url, "tags/level1-1.0")
        t.runner('svn co "{url}" "{path}"'.format(url=url, path=t.current_folder))

        # Export the recipe (be sure sources are retrieved from the repository)
        t.run("export . {ref}".format(ref=ref))
        package_layout = t.cache.package_layout(ref)
        exported_conanfile = load(package_layout.conanfile())
        self.assertNotIn("auto", exported_conanfile)
        os.remove(package_layout.scm_folder())

        t.run("install {ref} --build=lib".format(ref=ref))
        print(t.out)
        self.fail("AAA")
