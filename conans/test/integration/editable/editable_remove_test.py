import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestRemoveEditablePackageTest:

    @pytest.fixture()
    def client(self):
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . --name=lib --version=version --user=user --channel=name')
        t.run("editable list")
        assert "lib" in t.out
        return t

    def test_unlink(self, client):
        client.run('editable remove -r=lib/version@user/name')
        assert "Removed editable 'lib/version@user/name':" in client.out
        client.run("editable list")
        assert "lib" not in client.out

    def test_unlink_pattern(self, client):
        client.run('editable remove -r=*')
        assert "Removed editable 'lib/version@user/name':" in client.out
        client.run("editable list")
        assert "lib" not in client.out

    def test_remove_path(self, client):
        client.run("editable remove .")
        assert "Removed editable 'lib/version@user/name':" in client.out
        client.run("editable list")
        assert "lib" not in client.out

    def test_unlink_not_linked(self, client):
        client.run('editable remove -r=otherlib/version@user/name')
        assert "WARN: No editables were removed" in client.out
        client.run("editable list")
        assert "lib" in client.out
