import unittest

import time
from parameterized.parameterized import parameterized

from conans import DEFAULT_REVISION_V1
from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestServer, \
    TurboTestClient, GenConanfile
from conans.util.env_reader import get_env


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class InfoRevisions(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def test_info_command_showing_revision(self, v1):
        """If I run 'conan info ref' I get information about the revision only in a v2 client"""
        pass


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class ServerRevisionsIndexes(unittest.TestCase):
    def rotation_deleting_recipe_revisions_test(self):
        """
        - If we have two RREVs in the server and we remove the first one,
        the last one is the latest
        - If we have two RREvs in the server and we remove the second one,
        the first is now the latest
        """
        pass

    def rotation_deleting_package_revisions_test(self):
        """
        - If we have two PREVs in the server and we remove the first one,
        the last one is the latest
        - If we have two PREVs in the server and we remove the second one,
        the first is now the latest
        """
        pass

    def deleting_all_rrevs_test(self):
        """
        If we delete all the recipe revisions in the server. There is no latest.
        If then a client uploads a RREV it is the latest
        """
        pass

    def deleting_all_prevs_test(self):
        """
        If we delete all the package revisions in the server. There is no latest.
        If then a client uploads a RREV/PREV it is the latest
        """
        pass

    def rotation_of_latest_recipe_revision(self):
        """
        - If we upload a new RREV, is the latest
        """
        pass

    def rotation_of_latest_package_revision(self):
        """
        - If we upload a new PREV, is the latest
        """
        pass


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class UploadPackagesWithRevisions(unittest.TestCase):

    def setUp(self):
        self.c_v2 = TurboTestClient(revisions_enabled=True)
        self.c_v1 = TurboTestClient(revisions_enabled=False)
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def upload_a_recipe_test(self, v1):
        """If we upload a package to a server:
        1. Using v1 client it will upload "0" revision to the server. The rev time is NOT updated.
        2. Using v2 client it will upload RREV revision to the server. The rev time is NOT updated.
        """
        pass

    @parameterized.expand([(True,), (False,)])
    def upload_discarding_outdated_packages_test(self, v1):
        """If we upload all packages to a server,
           if a package doesn't belong to the current recipe:
        1. Using v1 client it will upload all the binaries as revision "0".
        2. Using v2 client it will upload only the matching packages.
        """
        pass

    @parameterized.expand([(True,), (False,)])
    def upload_no_overwrite_recipes_test(self, v1):
        """If we upload a RREV to the server and create a new RREV in the client,
        when we upload with --no-overwrite
        1. Using v1 client it will fail because it cannot overwrite.
        2. Using v2 client it will warn an upload a new revision.
        """
        pass

    @parameterized.expand([(True,), (False,)])
    def upload_no_overwrite_packages_test(self, v1):
        """If we upload a PREV to the server and create a new PREV in the client,
        when we upload with --no-overwrite
        1. Using v1 client it will fail because it cannot overwrite.
        2. Using v2 client it will warn an upload a new revision.
        """
        pass


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class SCMRevisions(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def explicit_revision_from_scm_test(self, v1):
        """If we use the SCM feature, the revision is taken from there. """
        pass

    @parameterized.expand([(True,), (False,)])
    def auto_revision_from_scm_test(self, v1):
        """If we use the SCM feature, the revision is detected from there.
         Also while we continue working in local, the revision doesn't change, so the packages
         can be found"""
        pass


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class SearchingPackagesWithRevisions(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

        # FIXME: Prepare here two RREVs in a remote,
        #  one with LINUX packages and second with WINDOWS packages

    @parameterized.expand([(True,), (False,)])
    def search_a_remote_package_without_rrev_test(self, v1):
        """If we search for the packages of a ref without specifying the RREV:

         - With an v1 client, it shows all the packages for all the revisions
         - With an v2 client, it shows the packages for the latest"""
        pass

    @parameterized.expand([(True,), (False,)])
    def search_a_local_package_without_rrev_test(self, v1):
        """If we search for the packages of a ref without specifying the RREV:

         - With an v1 client, it shows all the packages in local.
         - With an v2 client, it shows the packages in local for the latest, not showing the
           packages that doesn't belong to the recipe"""
        pass

    @parameterized.expand([(True,), (False,)])
    def search_a_remote_package_with_rrev_test(self, v1):
        """If we search for the packages of a ref specifying the RREV:
         1. With v2 client it shows the packages for that RREV
         2. With v1 client it fails, because it cannot propagate the rrev with v1"""
        pass

    @parameterized.expand([(True,), (False,)])
    def search_a_local_package_with_rrev_test(self, v1):
        """If we search for the packages of a ref specifying the RREV in the local cache:
         1. With v2 client it shows the packages for that RREV (only Linux)
         2. With v1 client it fails, because it cannot propagate the rrev with v1"""
        pass

    @parameterized.expand([(True,), (False,)])
    def search_in_local_by_pattern_test(self, v1):
        """If we search for recipes with a pattern:
         1. With v2 client it return the refs matching, the refs contain RREV
         2. With v1 client it return the refs matching, the refs without the RREV"""
        pass

    @parameterized.expand([(True,), (False,)])
    def search_in_remote_by_pattern_test(self, v1):
        """If we search for recipes with a pattern:
         1. With v2 client it return the refs matching of the latests, the refs contain RREV
         2. With v1 client it return the refs matching, the refs without the RREV"""

        # Upload to the server two rrevs for "lib" and two rrevs for "lib2"
        self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        pref1b = self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(self.ref)

        ref2 = ConanFileReference.loads("lib2/1.0@conan/testing")
        self.c_v2.create(ref2)
        self.c_v2.upload_all(ref2)

        pref2b = self.c_v2.create(ref2, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(ref2)

        # Search from the client for "lib*"

        client = self.c_v1 if v1 else self.c_v2
        client.remove_all()
        data = client.search("lib*", remote="default")
        items = data["results"][0]["items"]
        self.assertEquals(2, len(items))
        if v1:
            expected = [str(pref1b.ref), str(pref2b.ref)]
        else:
            expected = [pref1b.ref.full_repr(), pref2b.full_repr()]

        self.assertEquals(expected, [i["recipe"]["id"] for i in items])


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class CapabilitiesRevisionsTest(unittest.TestCase):

    def test_server_without_revisions_capability(self):
        """If a server doesn't have the revisions capability, a modern client will still
        talk v1"""
        pass


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class InstallingPackagesWithRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def test_install_binary_iterating_remotes(self, v1):
        """We have two servers (remote1 and remote2), both with a recipe and a package but the
        second one with a new
         PREV of the binary. If a client installs without specifying -r remote1, it will iterate
         remote2 also"""
        pass

    @parameterized.expand([(True,), (False,)])
    def test_update_recipe_iterating_remotes(self, v1):
        """We have two servers (remote1 and remote2), both with a recipe but the second one with a
        new RREV. If a client installs without specifying -r remote1, it WONT iterate
        remote2, because it is associated in the registry"""
        pass

    def test_update_pinned_rrev(self):
        """If I have a server with two RREV (RREV1 and RREV2) and two PREVs each (PREV1 and PREV2)
        if a client "install --update" pinning the RREV2 (being in the registry RREV1) it will
        install the PREV2 from the RREV2
        """
        pass

    def test_update_prev_only_same_rrev(self):
        """If I have a server with two RREV (RREV1 and RREV2) and RREV2 has two PREV, PREV1 and
        PREV2. If a client with RREV locally performs an install --update, it won't update PREV2
        because it doesn't belong to RREV1
        """
        pass

    def test_diamond_revisions_conflict(self):
        """ If we have a diamond because of pinned conflicting revisions in the requirements,
        it gives an error"""
        pass

    def test_alias(self):
        """ If an alias points to a RREV, it resolved that RREV and no other"""
        pass

    @parameterized.expand([(True,), (False,)])
    def test_install_rev0(self, v1):
        """If we upload a revision with a v1 client it is stored as rev0 in the server then:
         0. In the cache the revision is kept, not overwrite with the "0" & the timestamp is NOT
         updated.

         If we install it with a fresh client:

         1. With revisions enabled, it is 0 in the metadata, with None time (not supported)
         2. Without revisions,  it is 0 in the metadata, with not null time"""

        # Upload with v1
        pref = self.c_v1.create(self.ref)
        self.assertNotEquals(pref.revision, DEFAULT_REVISION_V1)
        self.assertNotEquals(pref.ref.revision, DEFAULT_REVISION_V1)

        remote_ref = self.c_v1.upload_all(self.ref)
        self.assertEquals(remote_ref.revision, DEFAULT_REVISION_V1)

        # Check remote revision and time
        remote_rev_time = self.server.recipe_revision_time(remote_ref)
        self.assertIsNotNone(remote_rev_time)

        local_rev, rev_time = self.c_v1.recipe_revision(self.ref)

        self.assertNotEquals(local_rev, DEFAULT_REVISION_V1)
        self.assertIsNone(rev_time)
        self.assertEquals(local_rev, pref.ref.revision)

        # Remove all from c_v1
        self.c_v1.remove_all()

        client = self.c_v1 if v1 else self.c_v2
        client.run("install {}".format(self.ref))
        local_rev, rev_time = client.recipe_revision(self.ref)
        local_prev, prev_time = client.package_revision(pref)
        self.assertEquals(local_rev, DEFAULT_REVISION_V1)
        if v1:
            self.assertIsNone(rev_time)
        else:
            self.assertIsNotNone(rev_time)  # Able to receive the time from the server

        self.assertEquals(local_prev, DEFAULT_REVISION_V1)

        if v1:
            self.assertIsNone(prev_time)
        else:
            self.assertIsNotNone(prev_time)  # Able to receive the time from the server

    def test_revision_metadata_update_on_install(self):
        """If a clean v2 client installs a RREV/PREV from a server, it get the time and
        the revision from upstream"""
        # Upload with v2
        pref = self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        rev_time_remote = self.server.recipe_revision_time(pref.ref)
        prev_time_remote = self.server.package_revision_time(pref)

        # Remove all from c_v2 local
        self.c_v2.remove_all()
        self.assertRaises(FileNotFoundError, self.c_v2.recipe_revision, self.ref)

        self.c_v2.run("install {}".format(self.ref))
        local_rev, rev_time = self.c_v2.recipe_revision(self.ref)
        local_prev, prev_time = self.c_v2.package_revision(pref)
        self.assertEquals(local_rev, pref.ref.revision)
        self.assertEquals(local_prev, pref.revision)

        self.assertEquals(rev_time, rev_time_remote)
        self.assertEquals(prev_time, prev_time_remote)

        self.assertIsNotNone(rev_time)
        self.assertIsNotNone(prev_time)

    def test_revision_metadata_update_on_update(self):
        """
        A client v2 upload a recipe revision
        Another client v2 upload a new recipe revision
        The first client can upgrade from the remote, getting the right time"""
        client = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        client2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})

        client.create(self.ref)
        client.upload_all(self.ref)

        time.sleep(1)  # Wait a second, to be considered an update
        pref = client2.create(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        client2.upload_all(self.ref)

        rrev_time_remote = self.server.recipe_revision_time(pref.ref)
        prev_time_remote = self.server.package_revision_time(pref)

        client.run("install {} --update".format(self.ref))
        self.assertIn("Package installed {}".format(pref.id), client.out)

        rrev, rrev_time = client.recipe_revision(self.ref)
        self.assertIsNotNone(rrev)
        self.assertIsNotNone(rrev_time)
        self.assertEquals(rrev_time, rrev_time_remote)

        prev, prev_time = client.package_revision(pref)
        self.assertIsNotNone(prev)
        self.assertIsNotNone(prev_time)
        self.assertEquals(prev_time, prev_time_remote)

    def test_revision_update_on_package_update(self):
        """
        A client v2 upload RREV with PREV1
        Another client v2 upload the same RREV with PREV2
        The first client can upgrade from the remote, getting the right time, only
        in the package, because the recipe is the same and it is not updated"""
        client = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        client2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})

        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_append({"MY_VAR": "1"}):
            pref = client.create(self.ref, conanfile=conanfile)
        client.upload_all(self.ref)

        time.sleep(1)  # Wait a second, to be considered an update
        with environment_append({"MY_VAR": "2"}):
            pref2 = client2.create(self.ref, conanfile=conanfile)

        client2.upload_all(self.ref)

        self.server.recipe_revision_time(pref.ref)
        prev1_time_remote = self.server.package_revision_time(pref)
        prev2_time_remote = self.server.package_revision_time(pref2)
        self.assertNotEquals(prev1_time_remote, prev2_time_remote)  # Two package revisions

        client.run("install {} --update".format(self.ref))
        self.assertIn("{} from 'default' - Cache".format(self.ref), client.out)
        self.assertIn("Retrieving package {}".format(pref.id), client.out)

        _, rrev_time = client.recipe_revision(self.ref)
        self.assertIsNone(rrev_time)  # Is None because it has not been downloaded

        prev, prev_time = client.package_revision(pref)
        self.assertIsNotNone(prev)
        self.assertIsNotNone(prev_time)
        # Local package revision time is the pref2
        self.assertEquals(prev_time, prev2_time_remote)

    @parameterized.expand([(True,), (False,)])
    def test_revision_miss_match_packages_in_local(self, v1):
        """If we have a recipe that doesn't match the local package:
         1. With revisions enabled, it is not resolved.
         2. Without revisions enabled it is resolved"""
        client = self.c_v1 if v1 else self.c_v2
        pref = client.create(self.ref)
        ref2 = client.export(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        # Now we have two RREVs and a PREV corresponding to the first one
        self.assertEquals(pref.ref.copy_clear_rev(), ref2.copy_clear_rev())
        self.assertNotEqual(pref.ref.revision, ref2.revision)

        # Now we try to install the self.ref, the binary is missing when using revisions
        command = "install {}".format(self.ref)
        if v1:
            client.run(command)
            self.assertIn("{} - Cache".format(pref), client.out)
        else:
            client.run(command, assert_error=True)
            self.assertIn("The package {} doesn't belong to the installed "
                          "recipe".format(pref), client.out)
            self.assertIn("ERROR: Missing prebuilt package for '{}'".format(self.ref), client.out)

    @parameterized.expand([(True,), (False,)])
    def test_revision_install_explicit_miss_match_rrev(self, v1):
        """If we have a recipe in local, but we request to install a different one with RREV
         1. With revisions enabled, it is removed and will look for it in the remotes
         2. Without revisions enabled it raises an input error"""
        client = self.c_v1 if v1 else self.c_v2
        ref = client.export(self.ref)
        command = "install {}#fakerevision --build missing".format(ref)
        if v1:
            client.run(command, assert_error=True)
            self.assertIn("ERROR: Revisions not enabled in the client, "
                          "specify a reference without revision", client.out)
        else:
            client.run(command, assert_error=True)
            self.assertIn("Different revision requested, "
                          "removing current local recipe...", client.out)
            self.assertIn("Unable to find '{}#fakerevision'".format(self.ref), client.out)

    @parameterized.expand([(True,), (False,)])
    def test_revision_miss_match_packages_remote(self, v1):
        """If we have a recipe that doesn't match a remote recipe:
         1. With revisions enabled, it is not resolved in the remote.
         2. Without revisions enabled it is resolved"""
        self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        client = self.c_v1 if v1 else self.c_v2
        client.remove_all()
        client.export(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        command = "install {}".format(self.ref)

        if v1:
            client.run(command)
        else:
            client.run(command, assert_error=True)
            self.assertIn("Can't find a '{}' package".format(self.ref), client.out)


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class RevisionsInLocalCacheTest(unittest.TestCase):

    def setUp(self):
        self.c_v2 = TurboTestClient(revisions_enabled=True)
        self.c_v1 = TurboTestClient(revisions_enabled=False)
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def test_create_metadata(self, v1):
        """When a create is executed, the recipe & package revision are updated in the cache"""
        client = self.c_v1 if v1 else self.c_v2
        pref = client.create(self.ref)
        # Check recipe revision
        rev, rev_time = client.recipe_revision(self.ref)
        self.assertEquals(pref.ref.revision, rev)
        self.assertIsNotNone(rev)
        self.assertIsNone(rev_time)  # Time is none until uploaded

        # Check package revision
        prev, prev_time = client.package_revision(pref)
        self.assertEquals(pref.revision, prev)
        self.assertIsNotNone(prev)
        self.assertIsNone(prev_time)

        # Create new revision, check that it changes
        client.create(self.ref, conanfile=GenConanfile().with_build_msg("Rev2"))
        rev2, rev_time2 = client.recipe_revision(self.ref)
        prev2, prev_time2 = client.package_revision(pref)

        self.assertNotEqual(rev2, rev)
        self.assertNotEqual(prev2, prev)

        self.assertIsNotNone(rev2)
        self.assertIsNotNone(prev2)
        self.assertIsNone(prev_time2)

    @parameterized.expand([(True,), (False,)])
    def test_export_metadata(self, v1):
        """When a export is executed, the recipe revision is updated in the cache"""
        client = self.c_v1 if v1 else self.c_v2
        ref = client.export(self.ref)
        # Check recipe revision
        rev, rev_time = client.recipe_revision(self.ref)
        self.assertEquals(ref.revision, rev)
        self.assertIsNotNone(rev)
        self.assertIsNone(rev_time)  # Time is none until uploaded

        # Export new revision, check that it changes
        client.export(self.ref, conanfile=GenConanfile().with_build_msg("Rev2"))
        rev2, rev_time2 = client.recipe_revision(self.ref)

        self.assertNotEqual(rev2, rev)
        self.assertIsNotNone(rev2)
        self.assertIsNone(rev_time2)


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class RemoveWithRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def test_remove_local_recipe(self, v1):
        """Locally:
            When I remove a recipe without RREV, everything is removed.
            When I remove a recipe with RREV only if the local revision matches is removed"""
        client = self.c_v1 if v1 else self.c_v2

        # If I remove the ref, the revision is gone, of course
        ref1 = client.export(self.ref)
        client.run("remove {} -f".format(ref1.copy_clear_rev().full_repr()))
        self.assertFalse(client.recipe_exists(self.ref))

        # If I remove a ref with a wrong revision, the revision is not removed
        ref1 = client.export(self.ref)
        full_ref = ref1.copy_with_rev("fakerev").full_repr()
        client.run("remove {} -f".format(full_ref), assert_error=True)
        self.assertIn("ERROR: No recipe found '%s'" % full_ref, client.out)
        self.assertTrue(client.recipe_exists(self.ref))
        self.assertIn("No recipe found 'lib/1.0@conan/testing#fakerev'", client.out)

    @parameterized.expand([(True,), (False,)])
    def test_remove_local_package(self, v1):
        """Locally:
            When I remove a recipe without RREV, the package is removed.
            When I remove a recipe with RREV only if the local revision matches is removed
            When I remove a package with PREV and not RREV it raises an error
            When I remove a package with RREV and PREV only when both matches is removed"""
        client = self.c_v1 if v1 else self.c_v2

        # If I remove the ref without RREV, the packages are also removed
        pref1 = client.create(self.ref)
        client.run("remove {} -f".format(pref1.ref.copy_clear_rev().full_repr()))
        self.assertFalse(client.package_exists(pref1))

        # If I remove the ref with fake RREV, the packages are not removed
        pref1 = client.create(self.ref)
        fakeref = pref1.ref.copy_with_rev("fakerev").full_repr()
        client.run("remove {} -f".format(fakeref), assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("No recipe found '{}'".format(fakeref), client.out)

        # If I remove the ref with valid RREV, the packages are removed
        pref1 = client.create(self.ref)
        client.run("remove {} -f".format(pref1.ref.full_repr()))
        self.assertFalse(client.package_exists(pref1))

        # If I remove the ref without RREV but specifying PREV it raises
        pref1 = client.create(self.ref)
        command = "remove {} -f -p {}#{}".format(pref1.ref.copy_clear_rev().full_repr(),
                                                 pref1.id, pref1.revision)
        client.run(command, assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("Specify a recipe revision if you specify a package revision", client.out)

        # A wrong PREV doesn't remove the PREV
        pref1 = client.create(self.ref)
        command = "remove {} -f -p {}#fakeprev".format(pref1.ref.full_repr(), pref1.id)
        client.run(command, assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("The package doesn't exist", client.out)

        # Everything correct, removes the unique local package revision
        pref1 = client.create(self.ref)
        command = "remove {} -f -p {}#{}".format(pref1.ref.full_repr(), pref1.id, pref1.revision)
        client.run(command)
        self.assertFalse(client.package_exists(pref1))

    @parameterized.expand([(True, ), (False, )])
    def test_remove_remote_recipe(self, v1):
        """When a client removes a reference, it removes ALL revisions, no matter
        if the client is v1 or v2"""
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        pref2 = self.c_v2.create(self.ref,
                                 conanfile=GenConanfile().with_build_msg("RREV 2!"))
        self.c_v2.upload_all(pref2.ref)

        self.assertNotEqual(pref1, pref2)

        remover_client = self.c_v1 if v1 else self.c_v2

        # Remove ref without revision in a remote
        remover_client.run("remove {} -f -r default".format(self.ref))
        self.assertFalse(self.server.recipe_exists(self.ref))
        self.assertFalse(self.server.recipe_exists(pref1.ref))
        self.assertFalse(self.server.recipe_exists(pref2.ref))
        self.assertFalse(self.server.package_exists(pref1))
        self.assertFalse(self.server.package_exists(pref2))

    @parameterized.expand([(True, ), (False, )])
    def test_remove_remote_recipe_revision(self, v1):
        """If a client removes a recipe with revision:
             - If the client is v1 will fail (it can't send the revision through the API)
             - If the client is v2 will remove only that revision"""
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        pref2 = self.c_v2.create(self.ref,
                                 conanfile=GenConanfile().with_build_msg("RREV 2!"))
        self.c_v2.upload_all(pref2.ref)

        self.assertNotEqual(pref1, pref2)

        remover_client = self.c_v1 if v1 else self.c_v2

        # Remove ref without revision in a remote
        command = "remove {} -f -r default".format(pref1.ref.full_repr())
        if v1:
            remover_client.run(command, assert_error=True)
            self.assertIn("Revisions not enabled in the client", remover_client.out)
        else:
            remover_client.run(command)
            self.assertFalse(self.server.recipe_exists(pref1.ref))
            self.assertTrue(self.server.recipe_exists(pref2.ref))

    @parameterized.expand([(True,), (False,)])
    def test_remove_remote_package(self, v1):
        """When a client removes a package, without RREV, it removes the package from ALL
        RREVs"""
        pref1 = self.c_v2.create(self.ref)
        self.c_v2.upload_all(pref1.ref)

        pref2 = self.c_v2.create(self.ref,
                                 conanfile=GenConanfile().with_build_msg("RREV 2!"))
        self.c_v2.upload_all(pref2.ref)

        self.assertEqual(pref1.id, pref2.id)
        # Locally only one revision exists at the same time
        self.assertFalse(self.c_v2.package_exists(pref1))
        self.assertTrue(self.c_v2.package_exists(pref2))

        remover_client = self.c_v1 if v1 else self.c_v2

        # Remove pref without RREV in a remote
        remover_client.run("remove {} -p {} -f -r default".format(self.ref, pref2.id))
        self.assertTrue(self.server.recipe_exists(pref1.ref))
        self.assertTrue(self.server.recipe_exists(pref2.ref))
        self.assertFalse(self.server.package_exists(pref1))
        self.assertFalse(self.server.package_exists(pref2))

    @parameterized.expand([(True,), (False,)])
    def test_remove_remote_package_revision(self, v1):
        """When a client removes a package with PREV
          (conan remove zlib/1.0@conan/stable -p 12312#PREV)
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
        with environment_append({"MY_VAR": "1"}):
            pref2 = self.c_v2.create(self.ref, conanfile=rev2_conanfile)
            self.c_v2.upload_all(pref2.ref)

        with environment_append({"MY_VAR": "2"}):
            pref2b = self.c_v2.create(self.ref, conanfile=rev2_conanfile)
            self.c_v2.upload_all(pref2b.ref)

        # Check created revisions
        self.assertEqual(pref1.id, pref2.id)
        self.assertEqual(pref2.id, pref2b.id)
        self.assertEqual(pref2.ref.revision, pref2b.ref.revision)
        self.assertNotEqual(pref2.revision, pref2b.revision)

        remover_client = self.c_v1 if v1 else self.c_v2

        # Remove PREV without RREV in a remote, the client has to fail
        command = "remove {} -p {}#{} -f -r default".format(self.ref, pref2.id, pref2.revision)
        remover_client.run(command, assert_error=True)
        self.assertIn("Specify a recipe revision if you specify a package revision",
                      remover_client.out)

        # Remove package with RREV and PREV
        command = "remove {} -p {}#{} -f -r default".format(pref2.ref.full_repr(),
                                                            pref2.id, pref2.revision)
        if v1:
            remover_client.run(command, assert_error=True)
            self.assertIn("Revisions not enabled in the client", remover_client.out)
        else:
            remover_client.run(command)
            self.assertTrue(self.server.recipe_exists(pref1.ref))
            self.assertTrue(self.server.recipe_exists(pref2.ref))
            self.assertTrue(self.server.recipe_exists(pref2b.ref))
            self.assertTrue(self.server.package_exists(pref1))
            self.assertTrue(self.server.package_exists(pref2b))
            self.assertFalse(self.server.package_exists(pref2))
