import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer, TurboTestClient, GenConanfile
from conans.util.env_reader import get_env


class DownloadRevisionsTest(unittest.TestCase):

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="No sense with revs")
    def test_download_revs_disabled_with_rrev(self):
        # https://github.com/conan-io/conan/issues/6106
        client = TestClient(revisions_enabled=False)
        client.run("download pkg/1.0@user/channel#fakerevision", assert_error=True)
        self.assertIn(
            "ERROR: Revisions not enabled in the client, specify a reference without revision",
            client.out)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_download_revs_enabled_with_fake_rrev(self):
        client = TestClient(default_server_user=True, revisions_enabled=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@user/channel")
        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#fakerevision", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/1.0@user/channel'", client.out)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_download_revs_enabled_with_rrev(self):
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True, revisions_enabled=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel --all --confirm")
        # create new revision from recipe
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@user/channel --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#{}".format(pref.ref.revision))
        self.assertIn("pkg/1.0@user/channel: Package installed {}".format(pref.id), client.out)
        search_result = client.search("pkg/1.0@user/channel --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_download_revs_enabled_with_rrev_no_user_channel(self):
        ref = ConanFileReference.loads("pkg/1.0@")
        servers = {"default": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                         users={"user": "password"})}
        client = TurboTestClient(servers=servers, revisions_enabled=True,
                                 users={"default": [("user", "password")]})
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@ --all --confirm")
        # create new revision from recipe
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@ --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@#{}".format(pref.ref.revision))
        self.assertIn("pkg/1.0: Package installed {}".format(pref.id), client.out)
        search_result = client.search("pkg/1.0@ --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_download_revs_enabled_with_prev(self):
        # https://github.com/conan-io/conan/issues/6106
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True, revisions_enabled=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel --all --confirm")
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@user/channel --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#{}:{}#{}".format(pref.ref.revision,
                                                                   pref.id,
                                                                   pref.revision))
        self.assertIn("pkg/1.0@user/channel: Package installed {}".format(pref.id), client.out)
        search_result = client.search("pkg/1.0@user/channel --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])
        search_result = client.search(
            "pkg/1.0@user/channel#{}:{} --revisions".format(pref.ref.revision, pref.id))[0]
        self.assertIn(pref.revision, search_result["revision"])
