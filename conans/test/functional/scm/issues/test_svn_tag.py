# coding=utf-8

import os
import textwrap

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.scm import SVNLocalRepoTestCase
from conans.test.utils.tools import TestClient, load


@pytest.mark.tool_svn
class SVNTaggedComponentTest(SVNLocalRepoTestCase):
    # Reproducing https://github.com/conan-io/conan/issues/5017

    def setUp(self):
        # Create a sample SVN repository
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class Lib(ConanFile):
                scm = {"type": "svn", "url": "auto", "revision": "auto"}
        """)
        files = {'trunk/level0.txt': "level0",
                 'trunk/level1/level1.txt': "level1",
                 'trunk/level1/conanfile.py': "invalid content",
                 'tags/sentinel': ""}
        self.project_url, _ = self.create_project(files=files)
        self.project_url = self.project_url.replace(" ", "%20")

        # Modify the recipe file and commit in trunk
        t = TestClient()
        t.run_command('svn co "{url}/trunk" "{path}"'.format(url=self.project_url,
                                                             path=t.current_folder))
        t.save({"level1/conanfile.py": conanfile})
        t.run_command('svn commit -m "created the conanfile"')

        # Create a tag for 'release 1.0'
        t.run_command('svn copy {url}/trunk {url}/tags/release-1.0'
                      ' -m "Release 1.0"'.format(url=self.project_url))

    def test_auto_tag(self):
        t = TestClient()
        ref = ConanFileReference.loads("lib/version@issue/testing")

        # Clone the tag to local folder
        url = os.path.join(self.project_url, "tags/release-1.0/level1").replace('\\', '/')
        t.run_command('svn co "{url}" "{path}"'.format(url=url, path=t.current_folder))

        # Export the recipe (be sure sources are retrieved from the repository)
        t.run("export . {ref}".format(ref=ref))
        package_layout = t.cache.package_layout(ref)
        exported_conanfile = load(package_layout.conanfile())
        self.assertNotIn("auto", exported_conanfile)
        self.assertIn('"revision": "3",', exported_conanfile)
        self.assertIn('tags/release-1.0/level1@3', exported_conanfile)
        t.run("remove {} -f -sf".format(ref))  # Remove sources caching

        # Compile (it will clone the repo)
        t.run("install {ref} --build=lib".format(ref=ref))
        self.assertIn("lib/version@issue/testing: SCM: Getting sources from url:", t.out)
