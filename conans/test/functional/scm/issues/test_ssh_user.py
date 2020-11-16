import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, load


@pytest.mark.tool_git
class GitSSHTest(unittest.TestCase):

    def test_ssh_username(self):
        t = TestClient()
        ref = ConanFileReference.loads("lib/version@issue/testing")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            
            class Conan(ConanFile):
                scm = {
                        "type": "git",
                        "url": "ssh://github.com/conan-io/conan.git",
                        "username": "git"}
        """)
        t.save({"conanfile.py": conanfile})

        t.run("export . {ref}".format(ref=ref))
        package_layout = t.cache.package_layout(ref)
        exported_conanfile = load(package_layout.conanfile())
        self.assertNotIn("auto", exported_conanfile)
        t.run("remove {} -f -sf".format(ref))  # Remove sources caching

        # Compile (it will clone the repo)
        t.run("install {ref} --build=lib".format(ref=ref))
        self.assertIn("lib/version@issue/testing: SCM: Getting sources from url:", t.out)
