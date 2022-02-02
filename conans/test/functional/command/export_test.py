import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient


class ExportMetadataTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Lib(ConanFile):
            revision_mode = "{revision_mode}"
    """)

    summary_hash = "bfe8b4a6a2a74966c0c4e0b34705004a"

    @pytest.mark.tool("git")
    def test_revision_mode_scm(self):
        t = TestClient()
        commit = t.init_git_repo({'conanfile.py': self.conanfile.format(revision_mode="scm")})

        ref = RecipeReference.loads("name/version@user/channel")
        t.run(f"export . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")

        latest_rev = t.cache.get_latest_recipe_reference(ref)

        self.assertEqual(latest_rev.revision, commit)
