import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class ExportMetadataTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Lib(ConanFile):
            revision_mode = "{revision_mode}"
    """)

    summary_hash = "bfe8b4a6a2a74966c0c4e0b34705004a"

    @pytest.mark.tool_git
    def test_revision_mode_scm(self):
        t = TestClient()
        commit = t.init_git_repo({'conanfile.py': self.conanfile.format(revision_mode="scm")})

        ref = ConanFileReference.loads("name/version@user/channel")
        t.run("export . {}".format(ref))

        meta = t.cache.package_layout(ref, short_paths=False).load_metadata()
        self.assertEqual(meta.recipe.revision, commit)
