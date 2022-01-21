import copy
from collections import OrderedDict

import pytest
from mock import patch

from conans.model.recipe_ref import RecipeReference
from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID


class TestSelectedRemotesInstall:
    @pytest.fixture(autouse=True)
    def _setup(self):
        servers = OrderedDict()
        for index in range(3):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})
        self.client = TestClient(servers=servers, inputs=3*["user", "password"])

    def test_revision_fixed_version(self):
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0").with_build_msg("OLDREV")})
        self.client.run("create .")
        self.client.run("upload liba -r server0 -c")
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0").with_build_msg("NEWER_REV")})
        self.client.run("create .")
        self.client.run("upload liba -r server1 -c")
        self.client.run("install --reference=liba/1.0 -r server0 -r server1")
        print(self.client.out)
