from collections import OrderedDict

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer


class TestSelectedRemotesInstall:
    @pytest.fixture(autouse=True)
    def _setup(self):
        servers = OrderedDict()
        for index in range(3):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})
        self.client = TestClient(servers=servers, inputs=3 * ["user", "password"])

    def test_selected_remotes(self):
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0").with_build_msg("OLDREV")})
        self.client.run("create .")
        self.client.run("upload liba/1.0 -r server0 -c")
        self.client.run("remove * -c")
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0").with_build_msg("NEWER_REV")})
        self.client.run("create .")
        self.client.run("upload liba/1.0 -r server1 -c")
        self.client.run("remove * -c")

        self.client.run("install --requires=liba/1.0 -r server0 -r server1 --build='*'")
        # we install the revision from the server with more preference
        assert "OLDREV" in self.client.out
        self.client.run("remove * -c")
        self.client.run("install --requires=liba/1.0 -r server1 -r server0 --build='*'")
        # changing the order of the remotes in the arguments does change the result
        # we install the revision from the server with more preference
        assert "NEWER_REV" in self.client.out
        # select two remotes, just one has liba, will install the rev from that one
        self.client.run("remove * -c")
        self.client.run("install --requires=liba/1.0 -r server2 -r server1 --build='*'")
        assert "NEWER_REV" in self.client.out

        self.client.save({"consumer.py": GenConanfile().with_require("liba/1.0")})
        self.client.run("remove * -c")
        self.client.run("create . --build='*' -r server0 -r server1 -r server2")
        assert "NEWER_REV" in self.client.out

    def test_upload_raise_multiple_remotes(self):
        self.client.run("upload liba -r server0 -r server1 -c", assert_error=True)
        assert "conan upload: error: -r can only be specified once" in self.client.out

    def test_remove_raise_multiple_remotes(self):
        self.client.run("remove liba -r server0 -r server1 -c", assert_error=True)
        assert "conan remove: error: -r can only be specified once" in self.client.out
