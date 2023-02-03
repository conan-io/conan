from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestEditablePackageTest:

    def test_install_ok(self):
        ref = RecipeReference.loads('lib/version@user/name')
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . {}'.format(ref))
        assert "Reference 'lib/version@user/name' in editable mode" in t.out

    def test_editable_list_search(self):
        ref = RecipeReference.loads('lib/version@user/name')
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . {}'.format(ref))
        t.run("editable list")
        assert "lib/version@user/name" in t.out
        assert "    Path:" in t.out

    def test_missing_subarguments(self):
        t = TestClient()
        t.run("editable", assert_error=True)
        assert "ERROR: Exiting with code: 2" in t.out

    def test_conanfile_name(self):
        t = TestClient()
        t.save({'othername.py': GenConanfile("lib", "version")})
        t.run('editable add ./othername.py lib/version@user/name')
        assert "Reference 'lib/version@user/name' in editable mode" in t.out
        t.run('install --requires=lib/version@user/name')
        t.assert_listed_require({"lib/version@user/name": "Editable"})
