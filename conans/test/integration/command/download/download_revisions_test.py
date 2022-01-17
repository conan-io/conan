import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, TestServer, TurboTestClient, GenConanfile


class DownloadRevisionsTest(unittest.TestCase):

    def test_download_revs_enabled_with_fake_rrev(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@user/channel")
        client.run("upload * --all --confirm -r default")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#fakerevision", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/1.0@user/channel#fakerevision'", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_download_revs_enabled_with_rrev(self):
        ref = RecipeReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel --all --confirm -r default")
        # create new revision from recipe
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@user/channel --all --confirm -r default")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#{}".format(pref.ref.revision))
        self.assertIn("pkg/1.0@user/channel: Package installed {}".format(pref.package_id),
                      client.out)
        search_result = client.search("pkg/1.0@user/channel --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_download_revs_enabled_with_rrev_no_user_channel(self):
        ref = RecipeReference.loads("pkg/1.0@")
        servers = {"default": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                         users={"user": "password"})}
        client = TurboTestClient(servers=servers, inputs=["admin", "password"])
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@ --all --confirm -r default")
        # create new revision from recipe
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@ --all --confirm -r default")
        client.run("remove * -f")
        client.run("download pkg/1.0@#{}".format(pref.ref.revision))
        self.assertIn("pkg/1.0: Package installed {}".format(pref.package_id), client.out)
        search_result = client.search("pkg/1.0@ --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_download_revs_enabled_with_prev(self):
        # https://github.com/conan-io/conan/issues/6106
        ref = RecipeReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel --all --confirm -r default")
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@user/channel --all --confirm -r default")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#{}:{}#{}".format(pref.ref.revision,
                                                                   pref.package_id,
                                                                   pref.revision))
        self.assertIn("pkg/1.0@user/channel: Package installed {}".format(pref.package_id),
                      client.out)
        search_result = client.search("pkg/1.0@user/channel --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])
        search_result = client.search(
            "pkg/1.0@user/channel#{}:{} --revisions".format(pref.ref.revision, pref.package_id))[0]
        self.assertIn(pref.revision, search_result["revision"])
