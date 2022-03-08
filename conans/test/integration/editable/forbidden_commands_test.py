# coding=utf-8

import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class ForbiddenRemoveTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_remove(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class APck(ConanFile):
                pass
            """)
        ref = RecipeReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': conanfile,
                      "mylayout": "", })
        t.run("export . --name=lib --version=version --user=user --channel=name")
        t.run('editable add . {}'.format(ref))
        self.assertTrue(t.cache.installed_as_editable(ref))
        t.run('remove {} --force'.format(ref), assert_error=True)
        self.assertIn("Package 'lib/version@user/name' is installed as editable, remove it first "
                      "using command 'conan editable remove lib/version@user/name'", t.out)

        # Also with a pattern, but only a warning
        t.run('remove lib* --force')
        self.assertIn("WARN: Package 'lib/version@user/name' is installed as editable, "
                      "remove it first using command 'conan editable remove lib/version@user/name'",
                      t.out)
        self.assertTrue(t.cache.installed_as_editable(ref))


class ForbiddenCommandsTest(unittest.TestCase):

    def setUp(self):
        self.ref = RecipeReference.loads('lib/version@user/name')
        self.t = TestClient(default_server_user=True)
        self.t.save({'conanfile.py': GenConanfile()})
        self.t.run('editable add . {}'.format(self.ref))

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_export(self):
        self.t.run('export . {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_create(self):
        self.t.run('create . {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_create_update(self):
        self.t.run('create . {} --update'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_upload(self):
        self.t.run('upload --force {} -r default'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_export_pkg(self):
        self.t.run('export-pkg -f . {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)
