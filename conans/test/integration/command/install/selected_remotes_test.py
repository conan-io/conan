from collections import OrderedDict

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestSelectedRemotesInstall:
    @pytest.fixture(autouse=True)
    def _setup(self):
        servers = OrderedDict()
        for index in range(3):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})
        self.client = TestClient(servers=servers, inputs=3 * ["user", "password"])

    # remotes have to be reordered like the order in the registry
    def test_selected_remotes_install(self):
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0").with_build_msg("OLDREV")})
        self.client.run("create .")
        self.client.run("upload liba/1.0 -r server0 -c")
        self.client.run("remove * -f")
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0").with_build_msg("NEWER_REV")})
        self.client.run("create .")
        self.client.run("upload liba/1.0 -r server1 -c")
        self.client.run("remove * -f")
        self.client.run("install --reference=liba/1.0 -r server0 -r server1 --build")
        # we install the revision from the server with more preference
        assert "OLDREV" in self.client.out
        self.client.run("remove * -f")
        self.client.run("install --reference=liba/1.0 -r server1 -r server0 --build")
        # changing the order of the remotes in the arguments does not change the result
        # we install the revision from the server with more preference
        assert "OLDREV" in self.client.out

    # check multiple remotes is not allowed for several commands like upload, ...
    def test_upload_raise_multiple_remotes(self):
        self.client.run("upload liba -r server0 -r server1 -c", assert_error=True)
        assert "conan upload: error: -r can only be specified once" in self.client.out
