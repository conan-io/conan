import copy
import time
import unittest
from collections import OrderedDict

import pytest
from mock import patch

from conans.util.env import environment_update
from conans.errors import RecipeNotFoundException
from conans.model.recipe_ref import RecipeReference
from conans.server.revision_list import RevisionList
from conans.test.utils.tools import TestServer, TurboTestClient, GenConanfile, TestClient
from conans.util.env import get_env
from conans.util.files import load


@pytest.mark.artifactory_ready
class InstallingPackagesWithRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.server2 = TestServer()
        self.servers = OrderedDict([("default", self.server),
                                    ("remote2", self.server2)])
        self.c_v2 = TurboTestClient(servers=self.servers, inputs=2*["admin", "password"])
        self.ref = RecipeReference.loads("lib/1.0@conan/testing")

    def test_install_binary_iterating_remotes_same_rrev(self):
        """We have two servers (remote1 and remote2), first with a recipe but the
        second one with a PREV of the binary.
        If a client installs without specifying -r remote1, it will iterate remote2 also"""
        conanfile = GenConanfile().with_package_file("file.txt", env_var="MY_VAR")
        with environment_update({"MY_VAR": "1"}):
            pref = self.c_v2.create(self.ref, conanfile=conanfile)
        the_time = time.time()
        with patch.object(RevisionList, '_now', return_value=the_time):
            self.c_v2.upload_all(self.ref, remote="default")
        self.c_v2.run("remove {}#*:{} -c -r default".format(self.ref, pref.package_id))
        # Same RREV, different PREV
        with environment_update({"MY_VAR": "2"}):
            pref2 = self.c_v2.create(self.ref, conanfile=conanfile)

        the_time = the_time + 10.0
        with patch.object(RevisionList, '_now', return_value=the_time):
            self.c_v2.upload_all(self.ref, remote="remote2")
        self.c_v2.remove_all()

        self.assertEqual(pref.ref.revision, pref2.ref.revision)

        self.c_v2.run("install --requires={}".format(self.ref))
        self.c_v2.assert_listed_require({str(self.ref): "Downloaded (default)"})
        self.assertIn("Retrieving package {} from remote 'remote2'".format(pref.package_id),
                      self.c_v2.out)

    def test_diamond_revisions_conflict(self):
        """ If we have a diamond because of pinned conflicting revisions in the requirements,
        it gives an error"""

        # Two revisions of "lib1" to the server
        lib1 = RecipeReference.loads("lib1/1.0@conan/stable")
        lib1_pref = self.c_v2.create(lib1)
        self.c_v2.upload_all(lib1)
        lib1b_pref = self.c_v2.create(lib1, conanfile=GenConanfile().with_build_msg("Rev2"))
        self.c_v2.upload_all(lib1)

        # Lib2 depending of lib1
        self.c_v2.remove_all()
        lib2 = RecipeReference.loads("lib2/1.0@conan/stable")
        self.c_v2.create(lib2, conanfile=GenConanfile().with_requirement(lib1_pref.ref))
        self.c_v2.upload_all(lib2)

        # Lib3 depending of lib1b
        self.c_v2.remove_all()
        lib3 = RecipeReference.loads("lib3/1.0@conan/stable")
        self.c_v2.create(lib3, conanfile=GenConanfile().with_requirement(lib1b_pref.ref))
        self.c_v2.upload_all(lib3)

        # Project depending on both lib3 and lib2
        self.c_v2.remove_all()
        project = RecipeReference.loads("project/1.0@conan/stable")
        self.c_v2.create(project,
                         conanfile=GenConanfile().with_requirement(lib2).with_requirement(lib3),
                         assert_error=True)
        self.assertIn("ERROR: Version conflict", self.c_v2.out)
        # self.assertIn("Different revisions of {} has been requested".format(lib1), self.c_v2.out)

    def test_alias_to_a_rrev(self):
        """ If an alias points to a RREV, it resolved that RREV and no other"""

        # Upload one revision
        pref = self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        # Upload other revision
        self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("Build Rev 2"))
        self.c_v2.upload_all(self.ref)
        self.c_v2.remove_all()

        # Create an alias to the first revision
        self.c_v2.alias("lib/latest@conan/stable", repr(pref.ref))
        alias_ref = RecipeReference.loads("lib/latest@conan/stable")
        exported = load(self.c_v2.get_latest_ref_layout(alias_ref).conanfile())
        self.assertIn('alias = "{}"'.format(repr(pref.ref)), exported)

        self.c_v2.upload_all(RecipeReference.loads("lib/latest@conan/stable"))
        self.c_v2.remove_all()

        self.c_v2.run("install --requires=lib/(latest)@conan/stable")
        # Shouldn't be packages in the cache
        self.assertNotIn("doesn't belong to the installed recipe revision", self.c_v2.out)

        # Read current revision
        self.assertEqual(pref.ref.revision, self.c_v2.recipe_revision(self.ref))

    def test_revision_metadata_update_on_install(self):
        """If a clean v2 client installs a RREV/PREV from a server, it get
        the revision from upstream"""
        # Upload with v2
        pref = self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        # Remove all from c_v2 local
        self.c_v2.remove_all()
        assert len(self.c_v2.cache.get_recipe_revisions_references(self.ref)) == 0

        self.c_v2.run("install --requires={}".format(self.ref))
        local_rev = self.c_v2.recipe_revision(self.ref)
        local_prev = self.c_v2.package_revision(pref)
        self.assertEqual(local_rev, pref.ref.revision)
        self.assertEqual(local_prev, pref.revision)

    @pytest.mark.xfail(reason="cache2.0 rewrite with db info instead of metadata")
    def test_revision_metadata_update_on_update(self):
        """
        A client v2 upload a recipe revision
        Another client v2 upload a new recipe revision
        The first client can upgrade from the remote"""
        client = TurboTestClient(servers={"default": self.server})
        client2 = TurboTestClient(servers={"default": self.server})

        pref1 = client.create(self.ref)
        client.upload_all(self.ref)

        rrev1_time_remote = self.server.recipe_revision_time(pref1.ref)
        prev1_time_remote = self.server.package_revision_time(pref1)

        time.sleep(1)  # Wait a second, to be considered an update
        pref2 = client2.create(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        client2.upload_all(self.ref)

        rrev2_time_remote = self.server.recipe_revision_time(pref2.ref)
        prev2_time_remote = self.server.package_revision_time(pref2)

        # Check different revision times
        self.assertNotEqual(rrev1_time_remote, rrev2_time_remote)
        self.assertNotEqual(prev1_time_remote, prev2_time_remote)

        client.run("install --requires={} --update".format(self.ref))
        self.assertIn("Package installed {}".format(pref2.package_id), client.out)

        rrev = client.recipe_revision(self.ref)
        self.assertIsNotNone(rrev)

        prev = client.package_revision(pref2)
        self.assertIsNotNone(prev)

    def test_revision_update_on_package_update(self):
        """
        A client v2 upload RREV with PREV1
        Another client v2 upload the same RREV with PREV2
        The first client can upgrade from the remote, only
        in the package, because the recipe is the same and it is not updated"""
        client = TurboTestClient(servers={"default": self.server}, inputs=["admin", "password"])
        client2 = TurboTestClient(servers={"default": self.server}, inputs=["admin", "password"])

        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_update({"MY_VAR": "1"}):
            pref = client.create(self.ref, conanfile=conanfile)

        time.sleep(1)

        with patch.object(RevisionList, '_now', return_value=time.time()):
            client.upload_all(self.ref)

        with environment_update({"MY_VAR": "2"}):
            pref2 = client2.create(self.ref, conanfile=conanfile)

        with patch.object(RevisionList, '_now', return_value=time.time() + 20.0):
            client2.upload_all(self.ref)

        prev1_time_remote = self.server.package_revision_time(pref)
        prev2_time_remote = self.server.package_revision_time(pref2)
        self.assertNotEqual(prev1_time_remote, prev2_time_remote)  # Two package revisions

        client.run("install --requires={} --update".format(self.ref))
        client.assert_listed_require({str(self.ref): "Cache (Updated date) (default)"})
        self.assertIn("Retrieving package {}".format(pref.package_id), client.out)

        prev = client.package_revision(pref)
        self.assertIsNotNone(prev)

    def test_revision_mismatch_packages_in_local(self):
        """Test adapted for the new cache: we create a revision but we export again a  recipe
        to create a new revision, then we won't have a package for the latest recipe revision
        of the cache.
        TODO: cache2.0 check this case"""
        client = self.c_v2
        pref = client.create(self.ref)
        ref2 = client.export(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        # Now we have two RREVs and a PREV corresponding to the first one
        sot1 = copy.copy(pref.ref)
        sot1.revision = None
        sot2 = copy.copy(ref2)
        sot2.revision = None
        self.assertEqual(sot1, sot2)
        self.assertNotEqual(pref.ref.revision, ref2.revision)

        # Now we try to install the self.ref, the binary is missing when using revisions
        command = "install --requires={}".format(self.ref)
        client.run(command, assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for '{}'".format(self.ref), client.out)

    def test_revision_install_explicit_mismatch_rrev(self):
        # If we have a recipe in local, but we request to install a different one with RREV
        # It fail and won't look the remotes unless --update
        client = self.c_v2
        ref = client.export(self.ref)
        command = "install --requires={}#fakerevision".format(ref)
        client.run(command, assert_error=True)
        self.assertIn("Unable to find '{}#fakerevision' in remotes".format(ref), client.out)
        command = "install --requires={}#fakerevision --update".format(ref)
        client.run(command, assert_error=True)
        self.assertIn("Unable to find '{}#fakerevision' in remotes".format(ref), client.out)

        # Now create a new revision with other client and upload it, we will request it
        new_client = TurboTestClient(servers=self.servers, inputs=["admin", "password"])
        pref = new_client.create(self.ref, conanfile=GenConanfile().with_build_msg("Rev2"))
        new_client.upload_all(self.ref)

        # Repeat the install --update pointing to the new reference
        client.run("install --requires={} --update".format(repr(pref.ref)))
        client.assert_listed_require({str(self.ref): "Downloaded (default)"})

    def test_revision_mismatch_packages_remote(self):
        """If we have a recipe that doesn't match a remote recipe:
         It is not resolved in the remote."""
        self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        client = self.c_v2
        client.remove_all()
        client.export(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        command = "install --requires={}".format(self.ref)

        client.run(command, assert_error=True)
        self.assertIn("Can't find a '{}' package".format(self.ref), client.out)


class RemoveWithRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(servers={"default": self.server}, inputs=["admin", "password"])
        self.ref = RecipeReference.loads("lib/1.0@conan/testing")

    def test_remove_local_recipe(self):
        """Locally: When I remove a recipe with RREV only if the local revision matches is removed"""
        client = self.c_v2

        # If I remove the ref, the revision is gone, of course
        ref1 = client.export(self.ref)
        ref1.revision = None
        client.run("remove {} -c".format(repr(ref1)))
        self.assertFalse(client.recipe_exists(self.ref))

        # If I remove a ref with a wrong revision, the revision is not removed
        ref1 = client.export(self.ref)
        fakeref = copy.copy(ref1)
        fakeref.revision = "fakerev"
        full_ref = repr(fakeref)
        client.run("remove {} -c".format(repr(fakeref)), assert_error=True)
        self.assertIn(f"ERROR: Recipe revision '{full_ref}' not found", client.out)
        self.assertTrue(client.recipe_exists(self.ref))

    def test_remove_local_package(self):
        """Locally:
            When I remove a recipe without RREV, the package is removed.
            When I remove a recipe with RREV only if the local revision matches is removed
            When I remove a package with PREV and not RREV it raises an error
            When I remove a package with RREV and PREV only when both matches is removed"""
        client = self.c_v2

        # If I remove the ref without RREV, the packages are also removed
        pref1 = client.create(self.ref)
        tmp = copy.copy(pref1.ref)
        tmp.revision = None
        client.run("remove {} -c".format(repr(tmp)))
        self.assertFalse(client.package_exists(pref1))

        # If I remove the ref with fake RREV, the packages are not removed
        pref1 = client.create(self.ref)
        fakeref = copy.copy(pref1.ref)
        fakeref.revision = "fakerev"
        str_ref = repr(fakeref)
        client.run("remove {} -c".format(repr(fakeref)), assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("Recipe revision '{}' not found".format(str_ref), client.out)

        # If I remove the ref with valid RREV, the packages are removed
        pref1 = client.create(self.ref)
        client.run("remove {} -c".format(repr(pref1.ref)))
        self.assertFalse(client.package_exists(pref1))

        # If I remove the ref without RREV but specifying PREV it raises
        pref1 = client.create(self.ref)
        tmp = copy.copy(pref1.ref)
        tmp.revision = None
        command = "remove {}:{}#{} -c".format(repr(tmp), pref1.package_id, pref1.revision)
        client.run(command)
        self.assertFalse(client.package_exists(pref1))

        # A wrong PREV doesn't remove the PREV
        pref1 = client.create(self.ref)
        command = "remove {}:{}#fakeprev -c".format(repr(pref1.ref), pref1.package_id)
        client.run(command, assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("ERROR: Package revision", client.out)

        # Everything correct, removes the unique local package revision
        pref1 = client.create(self.ref)
        command = "remove {}:{}#{} -c".format(repr(pref1.ref), pref1.package_id, pref1.revision)
        client.run(command)
        self.assertFalse(client.package_exists(pref1))

    def test_remove_remote_recipe(self):
        """When a client removes a reference, it removes ALL revisions, no matter
        if the client is v1 or v2"""
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        pref2 = self.c_v2.create(self.ref,
                                 conanfile=GenConanfile().with_build_msg("RREV 2!"))
        self.c_v2.upload_all(pref2.ref)

        self.assertNotEqual(pref1, pref2)

        remover_client = self.c_v2

        # Remove ref without revision in a remote
        remover_client.run("remove {} -c -r default".format(self.ref))
        self.assertFalse(self.server.recipe_exists(self.ref))
        self.assertFalse(self.server.recipe_exists(pref1.ref))
        self.assertFalse(self.server.recipe_exists(pref2.ref))
        self.assertFalse(self.server.package_exists(pref1))
        self.assertFalse(self.server.package_exists(pref2))

    def test_remove_remote_recipe_revision(self):
        """If a client removes a recipe with revision:
             - If the client is v2 will remove only that revision"""
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        pref2 = self.c_v2.create(self.ref,
                                 conanfile=GenConanfile().with_build_msg("RREV 2!"))
        self.c_v2.upload_all(pref2.ref)

        self.assertNotEqual(pref1, pref2)

        remover_client = self.c_v2

        # Remove ref without revision in a remote
        command = "remove {} -c -r default".format(repr(pref1.ref))
        remover_client.run(command)
        self.assertFalse(self.server.recipe_exists(pref1.ref))
        self.assertTrue(self.server.recipe_exists(pref2.ref))

    def test_remove_remote_package(self):
        """When a client removes a package, without RREV, it removes the package from ALL
        RREVs"""
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        pref2 = self.c_v2.create(self.ref,
                                 conanfile=GenConanfile().with_build_msg("RREV 2!"))
        self.c_v2.upload_all(pref2.ref)

        self.assertEqual(pref1.package_id, pref2.package_id)
        # Both revisions exist in 2.0 cache
        self.assertTrue(self.c_v2.package_exists(pref1))
        self.assertTrue(self.c_v2.package_exists(pref2))

        remover_client = self.c_v2

        # Remove pref without RREV in a remote
        remover_client.run("remove {}#*:{} -c -r default".format(self.ref, pref2.package_id))
        self.assertTrue(self.server.recipe_exists(pref1.ref))
        self.assertTrue(self.server.recipe_exists(pref2.ref))
        self.assertFalse(self.server.package_exists(pref1))
        self.assertFalse(self.server.package_exists(pref2))

    def test_remove_remote_package_revision(self):
        """When a client removes a package with PREV
          (conan remove zlib/1.0@conan/stable:12312#PREV)
            - If not RREV, the client fails
            - If RREV and PREV:
                - If v1 it fails in the client (cannot transmit revisions with v1)
                - If v2 it removes only that PREV
        """
        # First RREV
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        # Second RREV with two PREVS (exactly same conanfile, different package files)
        rev2_conanfile = GenConanfile().with_build_msg("RREV 2!")\
                                       .with_package_file("file", env_var="MY_VAR")
        with environment_update({"MY_VAR": "1"}):
            pref2 = self.c_v2.create(self.ref, conanfile=rev2_conanfile)
            self.c_v2.upload_all(pref2.ref)

        with environment_update({"MY_VAR": "2"}):
            pref2b = self.c_v2.create(self.ref, conanfile=rev2_conanfile)
            self.c_v2.upload_all(pref2b.ref)

        # Check created revisions
        self.assertEqual(pref1.package_id, pref2.package_id)
        self.assertEqual(pref2.package_id, pref2b.package_id)
        self.assertEqual(pref2.ref.revision, pref2b.ref.revision)
        self.assertNotEqual(pref2.revision, pref2b.revision)

        remover_client = self.c_v2

        # Remove PREV without RREV in a remote, the client has to fail
        command = "remove {}:{}#{} -c -r default".format(self.ref, pref2.package_id, pref2.revision)
        remover_client.run(command)

        self.assertTrue(self.server.recipe_exists(pref1.ref))
        self.assertTrue(self.server.recipe_exists(pref2.ref))
        self.assertTrue(self.server.recipe_exists(pref2b.ref))
        self.assertTrue(self.server.package_exists(pref1))
        self.assertTrue(self.server.package_exists(pref2b))
        self.assertFalse(self.server.package_exists(pref2))

        # Try to remove a missing revision
        command = "remove {}:{}#fakerev -c -r default".format(repr(pref2.ref), pref2.package_id)
        remover_client.run(command, assert_error=True)
        fakeref = copy.copy(pref2)
        fakeref.revision = "fakerev"
        self.assertIn(f"ERROR: Package revision '{fakeref.repr_notime()}' not found",
                      remover_client.out)


class SearchingPackagesWithRevisions(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.server2 = TestServer()
        servers = OrderedDict([("default", self.server),
                               ("remote2", self.server2)])
        self.c_v2 = TurboTestClient(servers=servers)
        self.ref = RecipeReference.loads("lib/1.0@conan/testing")

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_all_remotes_with_rrev(self):
        """If we search for the packages of a ref with the RREV in the "all" remote:

         - With an v2 client, it shows the packages for that specific RREV, in all the remotes,
           in an isolated way, just as we made it calling Conan N times

         No matter how many PREVS are uploaded it returns package references not duplicated"""
        # First revision with 1 binary, Windows
        # Second revision with 1 binary for Macos
        # Third revision with 2 binaries for SunOS and FreeBSD
        revisions = [{"os": "Windows"}], \
                    [{"os": "Macos"}], \
                    [{"os": "SunOS"}, {"os": "FreeBSD"}]
        refs = self.c_v2.massive_uploader(self.ref, revisions, remote="default", num_prev=2)
        self.c_v2.remove_all()
        # In the second remote only one revision, with one binary (two PREVS)
        revisions = [[{"os": "Linux"}]]
        refs2 = self.c_v2.massive_uploader(self.ref, revisions, remote="remote2", num_prev=2)
        self.c_v2.remove_all()

        # Ensure that the first revision in the first remote is the same than in the second one
        revision_ref = refs[0][0].ref
        self.assertEqual(revision_ref.revision, refs2[0][0].ref.revision)
        self.assertNotEqual(refs[1][0].ref.revision, refs2[0][0].ref.revision)

        # Check that in the remotes there are the packages we expect
        self.assertTrue(self.server.package_exists(refs[0][0]))
        self.assertTrue(self.server2.package_exists(refs2[0][0]))

        client = self.c_v2

        data = client.search(repr(revision_ref), remote="all")
        oss_r1 = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        oss_r2 = [p["settings"]["os"] for p in data["results"][1]["items"][0]["packages"]]
        self.assertEqual(["Windows"], oss_r1)
        self.assertEqual(["Linux"], oss_r2)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_all_remotes_without_rrev(self):
        """If we search for the packages of a ref without specifying the RREV in the "all" remote:

         - With an v2 client, it shows the packages for the latest, in all the remotes,
           in an isolated way, just as we made it calling Conan N times

         No matter how many PREVS are uploaded it returns package references not duplicated"""
        # First revision with 1 binary, Windows
        # Second revision with 1 binary for Macos
        # Third revision with 2 binaries for SunOS and FreeBSD
        revisions = [{"os": "Windows"}], \
                    [{"os": "Macos"}], \
                    [{"os": "SunOS"}, {"os": "FreeBSD"}]
        self.c_v2.massive_uploader(self.ref, revisions, remote="default", num_prev=2)
        self.c_v2.remove_all()
        # In the second remote only one revision, with one binary (two PREVS)
        revisions = [[{"os": "Linux"}]]
        self.c_v2.massive_uploader(self.ref, revisions, remote="remote2", num_prev=2)
        self.c_v2.remove_all()

        client = self.c_v2

        data = client.search(str(self.ref), remote="all")
        oss_r1 = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        oss_r2 = [p["settings"]["os"] for p in data["results"][1]["items"][0]["packages"]]
        self.assertEqual(set(["SunOS", "FreeBSD"]), set(oss_r1))
        self.assertEqual(set(["Linux"]), set(oss_r2))

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_a_remote_package_without_rrev(self):
        """If we search for the packages of a ref without specifying the RREV:

         - With an v2 client, it shows the packages for the latest

         No matter how many PREVS are uploaded it returns package references not duplicated"""

        # Upload to the server 3 RREVS for "lib" each one with 5 package_ids, each one with
        # 2 PREVS

        # First revision with 2 binaries, Windows and Linux
        # Second revision with 1 binary for Macos
        # Third revision with 2 binaries for SunOS and FreeBSD
        revisions = [{"os": "Windows"}, {"os": "Linux"}], \
                    [{"os": "Macos"}], \
                    [{"os": "SunOS"}, {"os": "FreeBSD"}]
        self.c_v2.massive_uploader(self.ref, revisions, num_prev=2)

        client = self.c_v2
        client.remove_all()

        data = client.search(str(self.ref), remote="default")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["SunOS", "FreeBSD"]), set(oss))

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_a_local_package_without_rrev(self):
        """If we search for the packages of a ref without specifying the RREV:

         - With an v2 client, it shows the packages in local for the latest, not showing the
           packages that doesn't belong to the recipe"""
        client = self.c_v2

        # Create two RREVs, first with Linux and Windows, second with Mac only (one PREV)
        conanfile = GenConanfile().with_build_msg("Rev1").with_setting("os")
        pref1a = client.create(self.ref, conanfile=conanfile, args="-s os=Linux")
        client.create(self.ref, conanfile=conanfile, args="-s os=Windows")

        conanfile2 = GenConanfile().with_build_msg("Rev2").with_setting("os")
        pref2a = client.create(self.ref, conanfile=conanfile2, args="-s os=Macos")

        self.assertNotEqual(pref1a.ref.revision, pref2a.ref.revision)

        # Search without RREV
        data = client.search(self.ref)
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]

        self.assertEqual(set(["Macos"]), set(oss))

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_a_remote_package_with_rrev(self):
        """If we search for the packages of a ref specifying the RREV:
         1. With v2 client it shows the packages for that RREV"""

        # Upload to the server two rrevs for "lib" and two rrevs for "lib2"
        conanfile = GenConanfile().with_build_msg("REV1").with_setting("os")
        pref = self.c_v2.create(self.ref, conanfile, args="-s os=Linux")
        self.c_v2.upload_all(self.ref)

        conanfile = GenConanfile().with_build_msg("REV2").with_setting("os")
        pref2 = self.c_v2.create(self.ref, conanfile, args="-s os=Windows")
        self.c_v2.upload_all(self.ref)

        # Ensure we have uploaded two different revisions
        self.assertNotEqual(pref.ref.revision, pref2.ref.revision)

        client = self.c_v2
        client.remove_all()
        data = client.search(repr(pref.ref), remote="default")
        items = data["results"][0]["items"][0]["packages"]
        self.assertEqual(1, len(items))
        oss = items[0]["settings"]["os"]
        self.assertEqual(oss, "Linux")

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_recipes_in_local_by_pattern(self):
        """If we search for recipes with a pattern:
         1. With v2 client it return the refs matching, the refs doesn't contain RREV"""

        client = self.c_v2
        # Create a couple of recipes locally
        client.export(self.ref)
        ref2 = RecipeReference.loads("lib2/1.0@conan/testing")
        client.export(ref2)

        # Search for the recipes
        data = client.search("lib*")
        items = data["results"][0]["items"]
        self.assertEqual(2, len(items))
        expected = [str(self.ref), str(ref2)]
        result = [i["recipe"]["id"] for i in items]
        # check if the reference is in the output
        # TODO: fix search output in 2.0
        assert [recipe for recipe in result if expected[0] in recipe]
        assert [recipe for recipe in result if expected[1] in recipe]

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_recipes_in_local_by_revision_pattern(self):
        """If we search for recipes with a pattern containing even the RREV:
         1. With v2 client it return the refs matching, the refs doesn't contain RREV"""

        client = self.c_v2
        # Create a couple of recipes locally
        client.export(self.ref)
        ref2 = RecipeReference.loads("lib2/1.0@conan/testing")
        client.export(ref2)

        # Search for the recipes
        data = client.search("{}*".format(repr(self.ref)))
        items = data["results"][0]["items"]
        self.assertEqual(1, len(items))
        expected = str(self.ref)
        result = items[0]["recipe"]["id"]
        self.assertIn(expected, result)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_recipes_in_remote_by_pattern(self):
        """If we search for recipes with a pattern:
         1. With v2 client it return the refs matching of the latests, the refs doesnt contain RREV"""

        # Upload to the server two rrevs for "lib" and two rrevs for "lib2"
        self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        pref1b = self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(self.ref)

        ref2 = RecipeReference.loads("lib2/1.0@conan/testing")
        self.c_v2.create(ref2)
        self.c_v2.upload_all(ref2)

        pref2b = self.c_v2.create(ref2, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(ref2)

        # Search from the client for "lib*"

        client = self.c_v2
        client.remove_all()
        data = client.search("lib*", remote="default")
        items = data["results"][0]["items"]
        self.assertEqual(2, len(items))
        expected = [str(pref1b.ref), str(pref2b.ref)]

        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    @pytest.mark.skipif(get_env("CONAN_TEST_WITH_ARTIFACTORY", False),
                        reason="Not implemented in artifactory")
    def test_search_in_remote_by_revision_pattern(self):
        """If we search for recipes with a pattern like "lib/1.0@conan/stable#rev*"
         1. With v2 client: We get the revs without refs matching the pattern

         The same for "lib/*@conan/stable#rev" and "*lib/*@conan/stable#rev"

         But if we search an invalid revision it is not found
         """

        # Upload to the server two rrevs for "lib" and one rrevs for "lib2"
        self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        pref2_lib = self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(self.ref)

        ref2 = RecipeReference.loads("lib2/1.0@conan/testing")
        self.c_v2.create(ref2)
        self.c_v2.upload_all(ref2)

        client = self.c_v2

        data = client.search("{}*".format(repr(pref2_lib.ref)), remote="default")
        items = data["results"][0]["items"]
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

        data = client.search("{}".format(repr(pref2_lib.ref)).replace("1.0", "*"),
                             remote="default")
        items = data["results"][0]["items"]
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

        data = client.search("*{}".format(repr(pref2_lib.ref)).replace("1.0", "*"),
                             remote="default")
        items = data["results"][0]["items"]
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

        data = client.search("*{}#fakerev".format(pref2_lib.ref),
                             remote="default")
        items = data["results"]
        expected = []
        self.assertEqual(expected, items)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_search_revisions_regular_results(self):
        """If I upload several revisions to a server, we can list the times"""
        server = TestServer()
        servers = OrderedDict([("default", server)])
        c_v2 = TurboTestClient(servers=servers)
        pref = c_v2.create(self.ref)
        c_v2.upload_all(self.ref)
        pref_rev = copy.copy(pref)
        pref_rev.revision = None

        c_v2.run("search {} --revisions -r default".format(repr(pref_rev)))
        # I don't want to mock here because I want to run this test against Artifactory
        self.assertIn("cf924fbb5ed463b8bb960cf3a4ad4f3a (", c_v2.out)
        self.assertIn(" UTC)", c_v2.out)


class UploadPackagesWithRevisions(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(servers={"default": self.server}, inputs=["admin", "password"])
        self.ref = RecipeReference.loads("lib/1.0@conan/testing")

    def test_upload_a_recipe(self):
        """If we upload a package to a server:
        Using v2 client it will upload RREV revision to the server. The rev time is NOT updated.
        """
        client = self.c_v2
        pref = client.create(self.ref)
        client.upload_all(self.ref)
        revs = [r.revision for r in self.server.server_store.get_recipe_revisions_references(self.ref)]

        self.assertEqual(revs, [pref.ref.revision])

    def test_upload_no_overwrite_recipes(self):
        """If we upload a RREV to the server and create a new RREV in the client,
        when we upload with --no-overwrite
        Using v2 client it will warn an upload a new revision.
        """
        client = self.c_v2
        pref = client.create(self.ref, conanfile=GenConanfile().with_setting("os"),
                             args=" -s os=Windows")
        client.upload_all(self.ref)
        pref2 = client.create(self.ref,
                              conanfile=GenConanfile().with_setting("os").with_build_msg("rev2"),
                              args=" -s os=Linux")

        self.assertEqual(self.server.server_store.get_last_revision(self.ref)[0], pref.ref.revision)
        client.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_revision(self.ref)[0], pref2.ref.revision)

    def test_upload_no_overwrite_packages(self):
        """If we upload a PREV to the server and create a new PREV in the client,
        when we upload with --no-overwrite
        Using v2 client it will warn and upload a new revision.
        """
        client = self.c_v2
        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_update({"MY_VAR": "1"}):
            pref = client.create(self.ref, conanfile=conanfile)
        client.upload_all(self.ref)

        with environment_update({"MY_VAR": "2"}):
            pref2 = client.create(self.ref, conanfile=conanfile)

        self.assertNotEqual(pref.revision, pref2.revision)

        self.assertEqual(self.server.server_store.get_last_package_revision(pref2).revision,
                         pref.revision)
        client.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref2).revision,
                         pref2.revision)


class SCMRevisions(unittest.TestCase):

    def test_auto_revision_even_without_scm_git(self):
        """
        Can't do conan create/export with uncommited changes if using revision_mode=scm
        """
        ref = RecipeReference.loads("lib/1.0@conan/testing")
        client = TurboTestClient()
        conanfile = GenConanfile().with_revision_mode("scm")
        commit = client.init_git_repo(files={"file.txt": "hey", "conanfile.py": str(conanfile)},
                                      origin_url="http://myrepo.git")
        client.create(ref, conanfile=conanfile)
        self.assertEqual(client.recipe_revision(ref), commit)

        # Change the conanfile and make another create, the revision should be the same
        client.save({"conanfile.py": str(conanfile.with_build_msg("New changes!"))})
        client.create(ref, conanfile=conanfile, assert_error=True)
        self.assertIn("Can't have a dirty repository using revision_mode='scm' and doing", client.out)

    def test_auto_revision_without_commits(self):
        """If we have a repo but without commits, it has to fail when the revision_mode=scm"""
        client = TurboTestClient()
        client.run_command('git init .')
        client.save({"conanfile.py": GenConanfile("lib", "0.1").with_revision_mode("scm")})
        client.run("create .", assert_error=True)
        # It error, because the revision_mode is explicitly set to scm
        self.assertIn("Cannot detect revision using 'scm' mode from repository", client.out)


class CapabilitiesRevisionsTest(unittest.TestCase):
    def test_server_with_only_v2_capability(self):
        server = TestServer(server_capabilities=[])
        c_v2 = TurboTestClient(servers={"default": server}, inputs=["admin", "password"])
        ref = RecipeReference.loads("lib/1.0@conan/testing")
        c_v2.create(ref)
        c_v2.upload_all(ref, remote="default")


class ServerRevisionsIndexes(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(servers={"default": self.server}, inputs=["admin", "password"])
        self.ref = RecipeReference.loads("lib/1.0@conan/testing")

    def test_rotation_deleting_recipe_revisions(self):
        """
        - If we have two RREVs in the server and we remove the first one,
        the last one is the latest
        - If we have two RREvs in the server and we remove the second one,
        the first is now the latest
        """
        ref1 = self.c_v2.export(self.ref, conanfile=GenConanfile())
        self.c_v2.upload_all(ref1)
        self.assertEqual(self.server.server_store.get_last_revision(self.ref).revision,
                         ref1.revision)
        ref2 = self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("I'm rev2"))
        self.c_v2.upload_all(ref2)
        self.assertEqual(self.server.server_store.get_last_revision(self.ref).revision,
                         ref2.revision)
        ref3 = self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("I'm rev3"))
        self.c_v2.upload_all(ref3)
        self.assertEqual(self.server.server_store.get_last_revision(self.ref).revision,
                         ref3.revision)

        revs = [r.revision for r in self.server.server_store.get_recipe_revisions_references(self.ref)]
        self.assertEqual(revs, [ref3.revision, ref2.revision, ref1.revision])
        self.assertEqual(self.server.server_store.get_last_revision(self.ref).revision,
                         ref3.revision)

        # Delete the latest from the server
        self.c_v2.run("remove {} -r default -c".format(repr(ref3)))
        revs = [r.revision for r in self.server.server_store.get_recipe_revisions_references(self.ref)]
        self.assertEqual(revs, [ref2.revision, ref1.revision])
        self.assertEqual(self.server.server_store.get_last_revision(self.ref).revision,
                         ref2.revision)

    def test_rotation_deleting_package_revisions(self):
        """
        - If we have two PREVs in the server and we remove the first one,
        the last one is the latest
        - If we have two PREVs in the server and we remove the second one,
        the first is now the latest
        """
        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_update({"MY_VAR": "1"}):
            pref1 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref1).revision,
                         pref1.revision)
        with environment_update({"MY_VAR": "2"}):
            pref2 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref1).revision,
                         pref2.revision)
        with environment_update({"MY_VAR": "3"}):
            pref3 = self.c_v2.create(self.ref, conanfile=conanfile)
        server_pref3 = self.c_v2.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref1).revision,
                         pref3.revision)

        self.assertEqual(pref1.ref.revision, pref2.ref.revision)
        self.assertEqual(pref2.ref.revision, pref3.ref.revision)
        self.assertEqual(pref3.ref.revision, server_pref3.revision)

        pref = copy.copy(pref1)
        pref.revision = None
        revs = [r.revision
                for r in self.server.server_store.get_package_revisions_references(pref)]
        self.assertEqual(revs, [pref3.revision, pref2.revision, pref1.revision])
        self.assertEqual(self.server.server_store.get_last_package_revision(pref).revision,
                         pref3.revision)

        # Delete the latest from the server
        self.c_v2.run("remove {}:{}#{} -r default -c".format(repr(pref3.ref),pref3.package_id,
                                                             pref3.revision))
        revs = [r.revision
                for r in self.server.server_store.get_package_revisions_references(pref)]
        self.assertEqual(revs, [pref2.revision, pref1.revision])
        self.assertEqual(self.server.server_store.get_last_package_revision(pref).revision,
                         pref2.revision)

    def test_deleting_all_rrevs(self):
        """
        If we delete all the recipe revisions in the server. There is no latest.
        If then a client uploads a RREV it is the latest
        """
        ref1 = self.c_v2.export(self.ref, conanfile=GenConanfile())
        self.c_v2.upload_all(ref1)
        ref2 = self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("I'm rev2"))
        self.c_v2.upload_all(ref2)
        ref3 = self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("I'm rev3"))
        self.c_v2.upload_all(ref3)

        self.c_v2.run("remove {} -r default -c".format(repr(ref1)))
        self.c_v2.run("remove {} -r default -c".format(repr(ref2)))
        self.c_v2.run("remove {} -r default -c".format(repr(ref3)))

        self.assertRaises(RecipeNotFoundException,
                          self.server.server_store.get_recipe_revisions_references, self.ref)

        ref4 = self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("I'm rev4"))
        self.c_v2.upload_all(ref4)

        revs = [r.revision for r in self.server.server_store.get_recipe_revisions_references(self.ref)]
        self.assertEqual(revs, [ref4.revision])

    def test_deleting_all_prevs(self):
        """
        If we delete all the package revisions in the server. There is no latest.
        If then a client uploads a RREV/PREV it is the latest
        """
        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_update({"MY_VAR": "1"}):
            pref1 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        with environment_update({"MY_VAR": "2"}):
            pref2 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        with environment_update({"MY_VAR": "3"}):
            pref3 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)

        # Delete the package revisions (all of them have the same ref#rev and id)
        command = "remove {}:{}#{{}} -r default -c".format(pref3.ref.repr_notime(), pref3.package_id)
        self.c_v2.run(command.format(pref3.revision))
        self.c_v2.run(command.format(pref2.revision))
        self.c_v2.run(command.format(pref1.revision))

        with environment_update({"MY_VAR": "4"}):
            pref4 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.run("upload {} -r default -c".format(pref4.repr_notime()))

        pref = copy.copy(pref1)
        pref.revision = None
        revs = [r.revision
                for r in self.server.server_store.get_package_revisions_references(pref)]
        self.assertEqual(revs, [pref4.revision])


def test_touching_other_server():
    # https://github.com/conan-io/conan/issues/9333
    servers = OrderedDict([("remote1", TestServer()),
                           ("remote2", None)])  # None server will crash if touched
    c = TestClient(servers=servers, inputs=["admin", "password"])
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . --name=pkg --version=0.1 --user=conan --channel=channel -s os=Windows")
    c.run("upload * -c -r=remote1")
    c.run("remove * -c")

    # This is OK, binary found
    c.run("install --requires=pkg/0.1@conan/channel -r=remote1 -s os=Windows")
    c.run("install --requires=pkg/0.1@conan/channel -r=remote1 -s os=Linux", assert_error=True)
    assert "ERROR: Missing binary: pkg/0.1@conan/channel" in c.out


def test_reupload_older_revision():
    """ upload maintains the server history
        https://github.com/conan-io/conan/issues/7331
    """
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    rrev1 = c.exported_recipe_revision()
    c.run("upload * -r=default -c")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("potato = 42")})
    c.run("export .")
    rrev2 = c.exported_recipe_revision()
    c.run("upload * -r=default -c")

    def check_order(inverse=False):
        c.run("list pkg/0.1#* -r=default")
        out = str(c.out)
        assert rrev1 in out
        assert rrev2 in out
        if inverse:
            assert out.find(rrev1) > out.find(rrev2)
        else:
            assert out.find(rrev1) < out.find(rrev2)

    check_order()

    # If we create the same older revision, and upload, still the same order
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    c.run("upload * -r=default -c")
    check_order()

    # Force doesn't change it, same order
    c.run("upload * -r=default -c --force")
    check_order()

    # the only way is to remove it, then upload
    c.run(f"remove pkg/0.1#{rrev1} -r=default -c")
    c.run("upload * -r=default -c --force")
    check_order(inverse=True)
