import os
import shutil

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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

    def test_removed_folder(self,):
        # https://github.com/conan-io/conan/issues/15038
        c = TestClient()
        c.save({'pkg/conanfile.py': GenConanfile()})
        c.run('editable add pkg --name=lib --version=version')
        shutil.rmtree(os.path.join(c.current_folder, "pkg"))
        # https://github.com/conan-io/conan/issues/16164
        # Making it possible, repeated issue
        c.run("editable remove pkg")
        assert "Removed editable 'lib/version'" in c.out
        c.run("editable list")
        assert "lib" not in c.out
