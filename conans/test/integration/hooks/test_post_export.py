# coding=utf-8

import os
import textwrap

import pytest
from mock import patch

from conans.client.hook_manager import HookManager
from conans.model.manifest import FileTreeManifest
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONAN_MANIFEST
from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="cache2.0 revisit test")
def test_called_before_digest(self):
    """ Test that 'post_export' hook is called before computing the digest of the
        exported folders
    """

    ref = RecipeReference.loads("name/version@user/channel")
    conanfile = textwrap.dedent("""\
        from conan import ConanFile

        class MyLib(ConanFile):
            pass
    """)

    t = TestClient()
    t.save({'conanfile.py': conanfile})
    ref_layout = t.get_latest_ref_layout(ref)

    def mocked_post_export(*args, **kwargs):
        # There shouldn't be a digest yet
        with self.assertRaisesRegex(IOError, "No such file or directory"):
            FileTreeManifest.load(ref_layout.export())
        self.assertFalse(os.path.exists(os.path.join(ref_layout.export(), CONAN_MANIFEST)))

    def mocked_load_hooks(hook_manager):
        hook_manager.hooks["post_export"] = [("_", mocked_post_export)]

    with patch.object(HookManager, "load_hooks", new=mocked_load_hooks):
        t.run(f"export . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
    self.assertTrue(os.path.exists(os.path.join(ref_layout.export(), CONAN_MANIFEST)))
