import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class CreateEditablePackageTest(unittest.TestCase):

    def test_install_ok(self):
        ref = RecipeReference.loads('lib/version@user/name')
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . {}'.format(ref))
        self.assertIn("Reference 'lib/version@user/name' in editable mode", t.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_editable_list_search(self):
        ref = RecipeReference.loads('lib/version@user/name')
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . {}'.format(ref))
        t.run("editable list")
        self.assertIn("lib/version@user/name", t.out)
        self.assertIn("    Path:", t.out)

        t.run("search")
        self.assertIn("lib/version@user/name", t.out)

    def test_missing_subarguments(self):
        t = TestClient()
        t.run("editable", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", t.out)

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_conanfile_name(self):
        t = TestClient()
        t.save({'othername.py': GenConanfile("lib", "version")})
        t.run('editable add ./othername.py lib/version@user/name')
        self.assertIn("Reference 'lib/version@user/name' in editable mode", t.out)
        t.run('install --reference=lib/version@user/name')
        self.assertIn("Installing package: lib/version@user/name", t.out)

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_search(self):
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . "lib/0.1@"')
        t.run('search lib/0.1@', assert_error=True)
        assert "Package in editable mode cannot list binaries" in t.out
