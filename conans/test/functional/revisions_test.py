import json
import os
import time
import unittest
from collections import OrderedDict

import pytest
from parameterized.parameterized import parameterized

from conans import DEFAULT_REVISION_V1, load, ONLY_V2
from conans.client.tools import environment_append
from conans.errors import RecipeNotFoundException, PackageNotFoundException
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestServer, TurboTestClient, GenConanfile, TestClient
from conans.util.env_reader import get_env
from conans.util.files import save


@pytest.mark.artifactory_ready
@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class InstallingPackagesWithRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.server2 = TestServer()
        self.servers = OrderedDict([("default", self.server),
                                    ("remote2", self.server2)])
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers=self.servers)
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers=self.servers)
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    def test_install_missing_prev_deletes_outdated_prev(self):
        """If we have in a local v2 client a RREV with a PREV that doesn't match the RREV, when
        we try to install, it removes the previous outdated PREV even before resolve it"""
        pref = self.c_v2.create(self.ref)
        self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))

        self.c_v2.run("install {} --build missing".format(self.ref))
        self.assertIn("WARN: The package {} doesn't belong to the installed recipe revision, "
                      "removing folder".format(pref), self.c_v2.out)
        self.assertIn("Package '{}' created".format(pref.id), self.c_v2.out)

    def test_install_binary_iterating_remotes_same_rrev(self):
        """We have two servers (remote1 and remote2), first with a recipe but the
        second one with a PREV of the binary.
        If a client installs without specifying -r remote1, it will iterate remote2 also"""
        conanfile = GenConanfile().with_package_file("file.txt", env_var="MY_VAR")
        with environment_append({"MY_VAR": "1"}):
            pref = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref, remote="default")
        self.c_v2.run("remove {} -p {} -f -r default".format(self.ref, pref.id))

        # Same RREV, different PREV
        with environment_append({"MY_VAR": "2"}):
            pref2 = self.c_v2.create(self.ref, conanfile=conanfile)

        self.c_v2.upload_all(self.ref, remote="remote2")
        self.c_v2.remove_all()

        self.assertEqual(pref.ref.revision, pref2.ref.revision)

        self.c_v2.run("install {}".format(self.ref))
        self.assertIn("{} from 'default' - Downloaded".format(self.ref), self.c_v2.out)
        self.assertIn("Retrieving package {} from remote 'remote2'".format(pref.id), self.c_v2.out)

    def test_install_binary_iterating_remotes_different_rrev(self):
        """We have two servers (remote1 and remote2), first with a recipe RREV1 but the
        second one with other RREV2 a PREV of the binary.
        If a client installs without specifying -r remote1, it wont find in remote2 the binary"""

        pref = self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("REv1"))
        self.c_v2.upload_all(self.ref, remote="default")
        self.c_v2.run("remove {} -p {} -f -r default".format(self.ref, pref.id))

        # Same RREV, different PREV
        pref = self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(self.ref, remote="remote2")
        self.c_v2.remove_all()

        # Install, it will iterate remotes, resolving the package from remote2, but the recipe
        # from default
        self.c_v2.run("install {}".format(self.ref), assert_error=True)
        self.assertIn("{} - Missing".format(pref), self.c_v2.out)

    def test_update_recipe_iterating_remotes(self):
        """We have two servers (remote1 and remote2), both with a recipe but the second one with a
        new RREV. If a client installs without specifying -r remote1, it WONT iterate
        remote2, because it is associated in the registry and have it in the cache. Unless we
        specify the -r remote2"""

        conanfile = GenConanfile().with_package_file("file.txt", env_var="MY_VAR")
        with environment_append({"MY_VAR": "1"}):
            pref = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref, remote="default")

        time.sleep(1)

        other_v2 = TurboTestClient(revisions_enabled=True, servers=self.servers)
        # Same RREV, different new PREV
        with environment_append({"MY_VAR": "2"}):
            other_v2.create(self.ref, conanfile=conanfile)
        other_v2.upload_all(self.ref, remote="remote2")

        # Install, it wont resolve the remote2 because it is in the registry, it will use the cache
        self.c_v2.run("install {} --update".format(self.ref))
        self.assertIn("lib/1.0@conan/testing:{} - Cache".format(pref.id), self.c_v2.out)

        # If we force remote2, it will find an update
        self.c_v2.run("install {} --update -r remote2".format(self.ref))
        self.assertIn("{} - Update".format(pref), self.c_v2.out)
        self.assertIn("Retrieving package {} from remote 'remote2' ".format(pref.id),
                      self.c_v2.out)

        # This is not updating the remote in the registry with a --update
        # Is this a bug?
        metadata = self.c_v2.cache.package_layout(self.ref).load_metadata()
        self.assertEqual("default", metadata.recipe.remote)

    def test_diamond_revisions_conflict(self):
        """ If we have a diamond because of pinned conflicting revisions in the requirements,
        it gives an error"""

        # Two revisions of "lib1" to the server
        lib1 = ConanFileReference.loads("lib1/1.0@conan/stable")
        lib1_pref = self.c_v2.create(lib1)
        self.c_v2.upload_all(lib1)
        lib1b_pref = self.c_v2.create(lib1, conanfile=GenConanfile().with_build_msg("Rev2"))
        self.c_v2.upload_all(lib1)

        # Lib2 depending of lib1
        self.c_v2.remove_all()
        lib2 = ConanFileReference.loads("lib2/1.0@conan/stable")
        self.c_v2.create(lib2, conanfile=GenConanfile().with_requirement(lib1_pref.ref))
        self.c_v2.upload_all(lib2)

        # Lib3 depending of lib1b
        self.c_v2.remove_all()
        lib3 = ConanFileReference.loads("lib3/1.0@conan/stable")
        self.c_v2.create(lib3, conanfile=GenConanfile().with_requirement(lib1b_pref.ref))
        self.c_v2.upload_all(lib3)

        # Project depending on both lib3 and lib2
        self.c_v2.remove_all()
        project = ConanFileReference.loads("project/1.0@conan/stable")
        self.c_v2.create(project,
                         conanfile=GenConanfile().with_requirement(lib2).with_requirement(lib3),
                         assert_error=True)
        self.assertIn("Conflict in {}\n ".format(lib3), self.c_v2.out)
        self.assertIn("Different revisions of {} has been requested".format(lib1), self.c_v2.out)

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
        self.c_v2.run("alias lib/latest@conan/stable {}".format(pref.ref.full_str()))
        alias_ref = ConanFileReference.loads("lib/latest@conan/stable")
        exported = load(self.c_v2.cache.package_layout(alias_ref).conanfile())
        self.assertIn('alias = "{}"'.format(pref.ref.full_str()), exported)

        self.c_v2.upload_all(ConanFileReference.loads("lib/latest@conan/stable"))
        self.c_v2.remove_all()

        self.c_v2.run("install lib/latest@conan/stable")
        # Shouldn't be packages in the cache
        self.assertNotIn("doesn't belong to the installed recipe revision", self.c_v2.out)

        # Read current revision
        self.assertEqual(pref.ref.revision, self.c_v2.recipe_revision(self.ref))

    @parameterized.expand([(True,), (False,)])
    def test_install_rev0(self, v1):
        """If we upload a revision with a v1 client it is stored as rev0 in the server then:
         0. In the cache the revision is kept, not overwrite with the "0"

         If we install it with a fresh client:

         1. With revisions enabled, it is 0 in the metadata (not supported)
         2. Without revisions,  it is 0 in the metadata"""

        # Upload with v1
        pref = self.c_v1.create(self.ref)
        self.assertNotEqual(pref.revision, DEFAULT_REVISION_V1)
        self.assertNotEqual(pref.ref.revision, DEFAULT_REVISION_V1)

        remote_ref = self.c_v1.upload_all(self.ref)
        self.assertEqual(remote_ref.revision, DEFAULT_REVISION_V1)

        # Check remote revision and time
        remote_rev_time = self.server.recipe_revision_time(remote_ref)
        self.assertIsNotNone(remote_rev_time)

        local_rev = self.c_v1.recipe_revision(self.ref)

        self.assertNotEqual(local_rev, DEFAULT_REVISION_V1)

        self.assertEqual(local_rev, pref.ref.revision)

        # Remove all from c_v1
        self.c_v1.remove_all()

        client = self.c_v1 if v1 else self.c_v2
        client.run("install {}".format(self.ref))
        local_rev = client.recipe_revision(self.ref)
        local_prev = client.package_revision(pref)
        self.assertEqual(local_rev, DEFAULT_REVISION_V1)
        self.assertEqual(local_prev, DEFAULT_REVISION_V1)

    def test_revision_metadata_update_on_install(self):
        """If a clean v2 client installs a RREV/PREV from a server, it get
        the revision from upstream"""
        # Upload with v2
        pref = self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        # Remove all from c_v2 local
        self.c_v2.remove_all()
        self.assertRaises(RecipeNotFoundException, self.c_v2.recipe_revision, self.ref)

        self.c_v2.run("install {}".format(self.ref))
        local_rev = self.c_v2.recipe_revision(self.ref)
        local_prev = self.c_v2.package_revision(pref)
        self.assertEqual(local_rev, pref.ref.revision)
        self.assertEqual(local_prev, pref.revision)

    def test_revision_metadata_update_on_update(self):
        """
        A client v2 upload a recipe revision
        Another client v2 upload a new recipe revision
        The first client can upgrade from the remote"""
        client = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        client2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})

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

        client.run("install {} --update".format(self.ref))
        self.assertIn("Package installed {}".format(pref2.id), client.out)

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

        prev1_time_remote = self.server.package_revision_time(pref)
        prev2_time_remote = self.server.package_revision_time(pref2)
        self.assertNotEqual(prev1_time_remote, prev2_time_remote)  # Two package revisions

        client.run("install {} --update".format(self.ref))
        self.assertIn("{} from 'default' - Cache".format(self.ref), client.out)
        self.assertIn("Retrieving package {}".format(pref.id), client.out)

        prev = client.package_revision(pref)
        self.assertIsNotNone(prev)

    @parameterized.expand([(True,), (False,)])
    def test_revision_mismatch_packages_in_local(self, v1):
        """If we have a recipe that doesn't match the local package:
         1. With revisions enabled, it is not resolved.
         2. Without revisions enabled it is resolved"""
        client = self.c_v1 if v1 else self.c_v2
        pref = client.create(self.ref)
        ref2 = client.export(self.ref, conanfile=GenConanfile().with_build_msg("REV2"))
        # Now we have two RREVs and a PREV corresponding to the first one
        self.assertEqual(pref.ref.copy_clear_rev(), ref2.copy_clear_rev())
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
    def test_revision_install_explicit_mismatch_rrev(self, v1):
        # If we have a recipe in local, but we request to install a different one with RREV
        # 1. With revisions enabled, it fail and won't look the remotes unless --update
        # 2. Without revisions enabled it raises an input error
        client = self.c_v1 if v1 else self.c_v2
        ref = client.export(self.ref)
        command = "install {}#fakerevision".format(ref)
        if v1:
            client.run(command, assert_error=True)
            self.assertIn("ERROR: Revisions not enabled in the client, "
                          "specify a reference without revision", client.out)
        else:
            client.run(command, assert_error=True)
            self.assertIn("The 'f3367e0e7d170aa12abccb175fee5f97' revision recipe in the local "
                          "cache doesn't match the requested 'lib/1.0@conan/testing#fakerevision'. "
                          "Use '--update' to check in the remote", client.out)
            command = "install {}#fakerevision --update".format(ref)
            client.run(command, assert_error=True)
            self.assertIn("Unable to find '{}#fakerevision' in remotes".format(ref), client.out)

            # Now create a new revision with other client and upload it, we will request it
            new_client = TurboTestClient(revisions_enabled=True, servers=self.servers)
            pref = new_client.create(self.ref, conanfile=GenConanfile().with_build_msg("Rev2"))
            new_client.upload_all(self.ref)

            # Repeat the install --update pointing to the new reference
            client.run("install {} --update".format(pref.ref.full_str()))
            self.assertIn("{} from 'default' - Downloaded".format(self.ref), client.out)

    @parameterized.expand([(True,), (False,)])
    def test_revision_mismatch_packages_remote(self, v1):
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
            self.assertIn("{}: Package installed".format(self.ref), client.out)
        else:
            client.run(command, assert_error=True)
            self.assertIn("Can't find a '{}' package".format(self.ref), client.out)

    def test_json_output(self):
        client = TurboTestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . {} --json file.json".format(self.ref.full_str()))
        data = json.loads(client.load("file.json"))
        ref = ConanFileReference.loads(data["installed"][0]["recipe"]["id"])
        self.assertIsNotNone(ref.revision)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class RevisionsInLocalCacheTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def test_create_metadata(self, v1):
        """When a create is executed, the recipe & package revision are updated in the cache"""
        client = self.c_v1 if v1 else self.c_v2
        pref = client.create(self.ref)
        # Check recipe revision
        rev = client.recipe_revision(self.ref)
        self.assertEqual(pref.ref.revision, rev)
        self.assertIsNotNone(rev)

        # Check package revision
        prev = client.package_revision(pref)
        self.assertEqual(pref.revision, prev)
        self.assertIsNotNone(prev)

        # Create new revision, check that it changes
        client.create(self.ref, conanfile=GenConanfile().with_build_msg("Rev2"))
        rev2 = client.recipe_revision(self.ref)
        prev2 = client.package_revision(pref)

        self.assertNotEqual(rev2, rev)
        self.assertNotEqual(prev2, prev)

        self.assertIsNotNone(rev2)
        self.assertIsNotNone(prev2)

    @parameterized.expand([(True,), (False,)])
    def test_new_exported_recipe_clears_outdated_packages(self, v1):
        client = self.c_v1 if v1 else self.c_v2
        conanfile = GenConanfile().with_setting("os")
        pref_outdated = client.create(self.ref, conanfile=conanfile, args="-s os=Windows")
        pref_ok = client.create(self.ref, conanfile=conanfile.with_build_msg("rev2"),
                                args="-s os=Linux")

        msg = "Removing the local binary packages from different recipe revisions"
        if v1:
            self.assertNotIn(msg, client.out)
            self.assertTrue(client.package_exists(pref_outdated.copy_clear_revs()))
        else:
            self.assertIn(msg, client.out)
            self.assertFalse(client.package_exists(pref_outdated.copy_clear_revs()))

        self.assertTrue(client.package_exists(pref_ok))

    @parameterized.expand([(True,), (False,)])
    def test_export_metadata(self, v1):
        """When a export is executed, the recipe revision is updated in the cache"""
        client = self.c_v1 if v1 else self.c_v2
        ref = client.export(self.ref)
        # Check recipe revision
        rev = client.recipe_revision(self.ref)
        self.assertEqual(ref.revision, rev)
        self.assertIsNotNone(rev)

        # Export new revision, check that it changes
        client.export(self.ref, conanfile=GenConanfile().with_build_msg("Rev2"))
        rev2 = client.recipe_revision(self.ref)

        self.assertNotEqual(rev2, rev)
        self.assertIsNotNone(rev2)

    def test_remove_metadata(self):
        """If I remote a package, the metadata is cleared"""
        pref = self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)
        self.c_v2.remove_all()
        self.c_v2.run("install {}".format(self.ref))

        self.c_v2.run("remove {} -p {} -f".format(pref.ref, pref.id))
        self.assertRaises(PackageNotFoundException, self.c_v2.package_revision, pref)
        rev = self.c_v2.recipe_revision(pref.ref)
        self.assertIsNotNone(rev)
        self.c_v2.remove_all()
        self.assertRaises(RecipeNotFoundException, self.c_v2.recipe_revision, pref.ref)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class RemoveWithRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    def test_remove_oudated_packages_locally_removes_orphan_prevs(self):
        """if we run 'conan remove --outdated' locally, it removes the PREVS belonging to a
        different RREV"""

        # V1 client exports two recipes, no packages are removed in the second
        # create, even belonging to a different recipe
        pref = self.c_v1.create(self.ref, conanfile=GenConanfile().with_setting("os"),
                                args="-s os=Windows")
        pref2 = self.c_v1.create(self.ref, conanfile=GenConanfile().with_setting("os").
                                 with_build_msg("I'm rev 2"),
                                 args="-s os=Linux")
        self.assertNotIn("Removing the local binary packages from different recipe revisions",
                         self.c_v1.out)

        # Now we enable the revisions in the c_v1, to make sure that with revisions
        # the orphan is also removed
        self.c_v1.enable_revisions()
        layout = self.c_v1.cache.package_layout(pref.ref.copy_clear_rev())

        # Assert pref (outdated) is in the cache
        self.assertTrue(layout.package_exists(pref.copy_clear_revs()))

        # Assert pref2 is also in the cache
        self.assertTrue(layout.package_exists(pref2.copy_clear_revs()))

        self.c_v1.run("remove {} --outdated -f".format(pref.ref))

        # Assert pref (outdated) is not in the cache anymore
        self.assertFalse(layout.package_exists(pref.copy_clear_revs()))

        # Assert pref2 is in the cache
        self.assertTrue(layout.package_exists(pref2.copy_clear_revs()))

    @parameterized.expand([(True,), (False,)])
    def test_remove_oudated_packages_remote(self, v1):
        """In a server with revisions uploaded no package is oudated so nothing is done, unless
        a v1 upload mixed packages to a v1 or some hardcoded revision happen"""
        self.c_v1.create(self.ref, conanfile=GenConanfile().
                         with_setting("os").
                         with_build_msg("I'm revision 1"),
                         args="-s os=Windows")
        self.c_v1.upload_all(self.ref)

        # Different revision, different package_id (but everything uploaded to rev0)
        self.c_v1.create(self.ref, conanfile=GenConanfile().
                         with_setting("os").
                         with_build_msg("I'm revision 2"),
                         args="-s os=Linux")
        self.c_v1.upload_all(self.ref)

        # Verify in the server there is only one revision "0"
        revs = self.server.server_store.get_recipe_revisions(self.ref)
        self.assertEqual([r.revision for r in revs], [DEFAULT_REVISION_V1])

        # Verify using v1 we can search for the outdated
        data = self.c_v1.search(self.ref, remote="default", args="--outdated")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["Windows"]), set(oss))
        self.assertTrue(data["results"][0]["items"][0]["packages"][0]["outdated"])

        # Verify we can remove it both using v1 or v2
        client = self.c_v1 if v1 else self.c_v2
        client.run("remove {} -r default --outdated -f".format(self.ref))

        # The Windows package is not there anymore
        data = self.c_v1.search(self.ref, remote="default", args="--outdated")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual([], oss)

        # But the Linux package is there, not outdated
        data = self.c_v1.search(self.ref, remote="default")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["Linux"]), set(oss))

    @parameterized.expand([(True,), (False,)])
    def test_remove_local_recipe(self, v1):
        """Locally:
            When I remove a recipe without RREV, everything is removed.
            When I remove a recipe with RREV only if the local revision matches is removed"""
        client = self.c_v1 if v1 else self.c_v2

        # If I remove the ref, the revision is gone, of course
        ref1 = client.export(self.ref)
        client.run("remove {} -f".format(ref1.copy_clear_rev().full_str()))
        self.assertFalse(client.recipe_exists(self.ref))

        # If I remove a ref with a wrong revision, the revision is not removed
        ref1 = client.export(self.ref)
        fakeref = ref1.copy_with_rev("fakerev")
        full_ref = fakeref.full_str() if not v1 else str(fakeref)
        client.run("remove {} -f".format(fakeref.full_str()), assert_error=True)
        self.assertIn("ERROR: Recipe not found: '%s'" % full_ref, client.out)
        self.assertTrue(client.recipe_exists(self.ref))

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
        client.run("remove {} -f".format(pref1.ref.copy_clear_rev().full_str()))
        self.assertFalse(client.package_exists(pref1))

        # If I remove the ref with fake RREV, the packages are not removed
        pref1 = client.create(self.ref)
        fakeref = pref1.ref.copy_with_rev("fakerev")
        str_ref = fakeref.full_str() if not v1 else str(fakeref)
        client.run("remove {} -f".format(fakeref.full_str()), assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("Recipe not found: '{}'".format(str_ref), client.out)

        # If I remove the ref with valid RREV, the packages are removed
        pref1 = client.create(self.ref)
        client.run("remove {} -f".format(pref1.ref.full_str()))
        self.assertFalse(client.package_exists(pref1))

        # If I remove the ref without RREV but specifying PREV it raises
        pref1 = client.create(self.ref)
        command = "remove {} -f -p {}#{}".format(pref1.ref.copy_clear_rev().full_str(),
                                                 pref1.id, pref1.revision)
        client.run(command, assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("Specify a recipe revision if you specify a package revision", client.out)

        # A wrong PREV doesn't remove the PREV
        pref1 = client.create(self.ref)
        command = "remove {} -f -p {}#fakeprev".format(pref1.ref.full_str(), pref1.id)
        client.run(command, assert_error=True)
        self.assertTrue(client.package_exists(pref1))
        self.assertIn("Binary package not found", client.out)

        # Everything correct, removes the unique local package revision
        pref1 = client.create(self.ref)
        command = "remove {} -f -p {}#{}".format(pref1.ref.full_str(), pref1.id, pref1.revision)
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
        command = "remove {} -f -r default".format(pref1.ref.full_str())
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
        command = "remove {} -p {}#{} -f -r default".format(pref2.ref.full_str(),
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

            # Try to remove a missing revision
            command = "remove {} -p {}#fakerev -f -r default".format(pref2.ref.full_str(),
                                                                     pref2.id)
            remover_client.run(command, assert_error=True)
            fakeref = pref2.copy_with_revs(pref2.ref.revision, "fakerev")
            self.assertIn("Binary package not found: '{}'".format(fakeref.full_str()),
                          remover_client.out)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class SearchingPackagesWithRevisions(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.server2 = TestServer()
        servers = OrderedDict([("default", self.server),
                               ("remote2", self.server2)])
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers=servers)
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers=servers)
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def test_search_outdated_packages_locally_without_rrev(self, v1):
        """If we search for the packages of a ref without specifying the RREV using --outdated:
           it shows the packages not matching the current recipe revision"""
        # Create locally a package outdated, because we export a new recipe revision
        self.c_v1.create(self.ref)
        ref = self.c_v1.export(self.ref, conanfile=GenConanfile().
                               with_build_msg("I'm your father, rev2"))

        if not v1:
            self.c_v1.enable_revisions()

        data = self.c_v1.search(ref, args="--outdated")
        self.assertTrue(data["results"][0]["items"][0]["packages"][0]["outdated"])

    @parameterized.expand([(True,), (False,)])
    def test_search_outdated_packages_locally_with_rrev(self, v1):
        """If we search for the packages of a ref specifying the RREV using --outdated:
            - If the RREV do not exists it will raise
            - If the RREV exists it won't show anything, if the recipe is there, is the current one
        """
        # Create locally a package outdated, because we export a new recipe revision
        client = self.c_v1 if v1 else self.c_v2
        client.create(self.ref)
        ref = client.export(self.ref, conanfile=GenConanfile().
                            with_build_msg("I'm your father, rev2"))

        data = client.search(ref.full_str(), args="--outdated")
        self.assertEqual([], data["results"][0]["items"][0]["packages"])

        client.search("{}#fakerev".format(ref), args="--outdated", assert_error=True)
        self.assertIn("Recipe not found: 'lib/1.0@conan/testing#fakerev'", client.out)

    def test_search_outdated_packages_remote(self):
        """If we search for outdated packages in a remote, it has to be
        always empty, unless it is the "0" revision that contain some mixed packages uploaded with
        a client with revisions disabled
        """
        self.c_v1.create(self.ref, conanfile=GenConanfile().
                         with_setting("os").
                         with_build_msg("I'm revision 1"),
                         args="-s os=Windows")
        self.c_v1.upload_all(self.ref)

        # Different revision, different package_id (but everything uploaded to rev0)
        self.c_v1.create(self.ref, conanfile=GenConanfile().
                         with_setting("os").
                         with_build_msg("I'm revision 2"),
                         args="-s os=Linux")
        self.c_v1.upload_all(self.ref)

        # Verify in the server there is only one revision "0"
        revs = self.server.server_store.get_recipe_revisions(self.ref)
        self.assertEqual([r.revision for r in revs], [DEFAULT_REVISION_V1])

        # Verify if we can reach both packages with v1 (The Windows is outdated)
        data = self.c_v1.search(self.ref, remote="default")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["Windows", "Linux"]), set(oss))

        # Verify using v1 we can search for the outdated
        data = self.c_v1.search(self.ref, remote="default", args="--outdated")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["Windows"]), set(oss))
        self.assertTrue(data["results"][0]["items"][0]["packages"][0]["outdated"])

        # Verify using v2 if we can get the outdated
        data = self.c_v2.search(self.ref, remote="default", args="--outdated")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["Windows"]), set(oss))
        self.assertTrue(data["results"][0]["items"][0]["packages"][0]["outdated"])

        # Verify using v2 and specifying RREV we can get the outdated
        data = self.c_v2.search(self.ref.copy_with_rev(DEFAULT_REVISION_V1),
                                remote="default", args="--outdated")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        self.assertEqual(set(["Windows"]), set(oss))
        self.assertTrue(data["results"][0]["items"][0]["packages"][0]["outdated"])

    @parameterized.expand([(True,), (False,)])
    def test_search_all_remotes_with_rrev(self, v1):
        """If we search for the packages of a ref with the RREV in the "all" remote:

         - With an v1 client, it fails
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

        client = self.c_v1 if v1 else self.c_v2

        if v1:
            client.search(revision_ref.full_str(), remote="all", assert_error=True)
            self.assertIn("ERROR: Revisions not enabled in the client, "
                          "specify a reference without revision", client.out)
        else:
            data = client.search(revision_ref.full_str(), remote="all")
            oss_r1 = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
            oss_r2 = [p["settings"]["os"] for p in data["results"][1]["items"][0]["packages"]]
            self.assertEqual(["Windows"], oss_r1)
            self.assertEqual(["Linux"], oss_r2)

    @parameterized.expand([(True,), (False,)])
    def test_search_all_remotes_without_rrev(self, v1):
        """If we search for the packages of a ref without specifying the RREV in the "all" remote:

         - With an v1 client, it shows all the packages for all the revisions, in all the remotes
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

        client = self.c_v1 if v1 else self.c_v2

        data = client.search(str(self.ref), remote="all")
        oss_r1 = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        oss_r2 = [p["settings"]["os"] for p in data["results"][1]["items"][0]["packages"]]
        if v1:
            self.assertEqual(set(["Windows", "Macos", "SunOS", "FreeBSD"]), set(oss_r1))
            self.assertEqual(set(["Linux"]), set(oss_r2))
        else:
            self.assertEqual(set(["SunOS", "FreeBSD"]), set(oss_r1))
            self.assertEqual(set(["Linux"]), set(oss_r2))

    @parameterized.expand([(True,), (False,)])
    def test_search_a_remote_package_without_rrev(self, v1):
        """If we search for the packages of a ref without specifying the RREV:

         - With an v1 client, it shows all the packages for all the revisions
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

        client = self.c_v1 if v1 else self.c_v2
        client.remove_all()

        data = client.search(str(self.ref), remote="default")
        oss = [p["settings"]["os"] for p in data["results"][0]["items"][0]["packages"]]
        if v1:
            self.assertEqual(set(["Linux", "Windows", "Macos", "SunOS", "FreeBSD"]), set(oss))
        else:
            self.assertEqual(set(["SunOS", "FreeBSD"]), set(oss))

    @parameterized.expand([(True,), (False,)])
    def test_search_a_local_package_without_rrev(self, v1):
        """If we search for the packages of a ref without specifying the RREV:

         - With an v1 client, it shows all the packages in local.
         - With an v2 client, it shows the packages in local for the latest, not showing the
           packages that doesn't belong to the recipe"""
        client = self.c_v1 if v1 else self.c_v2

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

        if v1:
            self.assertEqual(set(["Linux", "Windows", "Macos"]), set(oss))
        else:
            self.assertEqual(set(["Macos"]), set(oss))

    @parameterized.expand([(True,), (False,)])
    def test_search_a_remote_package_with_rrev(self, v1):
        """If we search for the packages of a ref specifying the RREV:
         1. With v2 client it shows the packages for that RREV
         2. With v1 client it fails, because it cannot propagate the rrev with v1"""

        # Upload to the server two rrevs for "lib" and two rrevs for "lib2"
        conanfile = GenConanfile().with_build_msg("REV1").with_setting("os")
        pref = self.c_v2.create(self.ref, conanfile, args="-s os=Linux")
        self.c_v2.upload_all(self.ref)

        conanfile = GenConanfile().with_build_msg("REV2").with_setting("os")
        pref2 = self.c_v2.create(self.ref, conanfile, args="-s os=Windows")
        self.c_v2.upload_all(self.ref)

        # Ensure we have uploaded two different revisions
        self.assertNotEqual(pref.ref.revision, pref2.ref.revision)

        client = self.c_v1 if v1 else self.c_v2
        client.remove_all()
        if v1:
            client.search(pref.ref.full_str(), remote="default", assert_error=True)
            self.assertIn("ERROR: Revisions not enabled in the client, specify "
                          "a reference without revision", client.out)
        else:
            data = client.search(pref.ref.full_str(), remote="default")
            items = data["results"][0]["items"][0]["packages"]
            self.assertEqual(1, len(items))
            oss = items[0]["settings"]["os"]
            self.assertEqual(oss, "Linux")

    @parameterized.expand([(True,), (False,)])
    def test_search_a_local_package_with_rrev(self, v1):
        """If we search for the packages of a ref specifying the RREV in the local cache:
         1. With v2 client it shows the packages for that RREV and only if it is the one
            in the cache, otherwise it is not returned.
         2. With v1 client: the same"""

        client = self.c_v1 if v1 else self.c_v2
        pref1 = client.create(self.ref, GenConanfile().with_setting("os").with_build_msg("Rev1"),
                              args="-s os=Windows")

        pref2 = client.create(self.ref, GenConanfile().with_setting("os").with_build_msg("Rev2"),
                              args="-s os=Linux")

        client.run("search {}".format(pref1.ref.full_str()), assert_error=True)
        self.assertIn("Recipe not found: '{}'".format(pref1.ref.full_str()), client.out)

        client.run("search {}".format(pref2.ref.full_str()))
        self.assertIn("Existing packages for recipe {}:".format(pref2.ref), client.out)
        self.assertIn("os: Linux", client.out)

    @parameterized.expand([(True,), (False,)])
    def test_search_recipes_in_local_by_pattern(self, v1):
        """If we search for recipes with a pattern:
         1. With v2 client it return the refs matching, the refs doesn't contain RREV
         2. With v1 client, same"""

        client = self.c_v1 if v1 else self.c_v2
        # Create a couple of recipes locally
        client.export(self.ref)
        ref2 = ConanFileReference.loads("lib2/1.0@conan/testing")
        client.export(ref2)

        # Search for the recipes
        data = client.search("lib*")
        items = data["results"][0]["items"]
        self.assertEqual(2, len(items))
        expected = [str(self.ref), str(ref2)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

    @parameterized.expand([(True,), (False,)])
    def test_search_recipes_in_local_by_revision_pattern(self, v1):
        """If we search for recipes with a pattern containing even the RREV:
         1. With v2 client it return the refs matching, the refs doesn't contain RREV
         2. With v1 client, same"""

        client = self.c_v1 if v1 else self.c_v2
        # Create a couple of recipes locally
        client.export(self.ref)
        ref2 = ConanFileReference.loads("lib2/1.0@conan/testing")
        client.export(ref2)

        # Search for the recipes
        data = client.search("{}*".format(self.ref.full_str()))
        items = data["results"][0]["items"]
        self.assertEqual(1, len(items))
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

    @parameterized.expand([(True,), (False,)])
    def test_search_recipes_in_remote_by_pattern(self, v1):
        """If we search for recipes with a pattern:
         1. With v2 client it return the refs matching of the latests, the refs doesnt contain RREV
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
        self.assertEqual(2, len(items))
        expected = [str(pref1b.ref), str(pref2b.ref)]

        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

    @parameterized.expand([(True,), (False,)])
    @pytest.mark.skipif(get_env("CONAN_TEST_WITH_ARTIFACTORY", False),
                        reason="Not implemented in artifactory")
    def test_search_in_remote_by_revision_pattern(self, v1):
        """If we search for recipes with a pattern like "lib/1.0@conan/stable#rev*"
         1. With v2 client: We get the revs without refs matching the pattern
         2. With v1 client: Same

         The same for "lib/*@conan/stable#rev" and "*lib/*@conan/stable#rev"

         But if we search an invalid revision it is not found
         """

        # Upload to the server two rrevs for "lib" and one rrevs for "lib2"
        self.c_v2.create(self.ref)
        self.c_v2.upload_all(self.ref)

        pref2_lib = self.c_v2.create(self.ref, conanfile=GenConanfile().with_build_msg("REv2"))
        self.c_v2.upload_all(self.ref)

        ref2 = ConanFileReference.loads("lib2/1.0@conan/testing")
        self.c_v2.create(ref2)
        self.c_v2.upload_all(ref2)

        client = self.c_v1 if v1 else self.c_v2

        data = client.search("{}*".format(pref2_lib.ref.full_str()), remote="default")
        items = data["results"][0]["items"]
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

        data = client.search("{}".format(pref2_lib.ref.full_str()).replace("1.0", "*"),
                             remote="default")
        items = data["results"][0]["items"]
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

        data = client.search("*{}".format(pref2_lib.ref.full_str()).replace("1.0", "*"),
                             remote="default")
        items = data["results"][0]["items"]
        expected = [str(self.ref)]
        self.assertEqual(expected, [i["recipe"]["id"] for i in items])

        data = client.search("*{}#fakerev".format(pref2_lib.ref),
                             remote="default")
        items = data["results"]
        expected = []
        self.assertEqual(expected, items)

    def test_search_revisions_locally_with_v1_server(self):
        """If I upload a recipe to a v1 server and then I check the revisions locally, it
        will return None to the time because the v1 doesn't support revisions"""
        old_server = TestServer(server_capabilities=[])
        servers = OrderedDict([("default", old_server)])
        c_v1 = TurboTestClient(revisions_enabled=False, servers=servers)
        pref = c_v1.create(self.ref)
        c_v1.upload_all(self.ref)
        c_v1.enable_revisions()

        # Local searchs
        c_v1.run("search {} --revisions".format(pref.ref))
        self.assertIn("{} (No time)".format(pref.ref.revision), c_v1.out)

        pref_rev = pref.copy_with_revs(pref.ref.revision, None)
        c_v1.run("search {} --revisions".format(pref_rev.full_str()))
        self.assertIn("{} (No time)".format(pref.revision), c_v1.out)

    def test_search_revisions_remotely_with_v1_server(self):
        """If I upload a recipe to a v1 server and then I check the revisions locally, it
        will return None to the time because the v1 doesn't support revisions"""
        old_server = TestServer(server_capabilities=[])
        servers = OrderedDict([("default", old_server)])
        c_v1 = TurboTestClient(revisions_enabled=False, servers=servers)
        pref = c_v1.create(self.ref)
        c_v1.upload_all(self.ref)
        c_v1.enable_revisions()

        # Local searchs
        c_v1.run("search {} --revisions -r default".format(pref.ref), assert_error=True)
        self.assertIn("The remote doesn't support revisions", c_v1.out)

        pref_rev = pref.copy_with_revs(pref.ref.revision, None)
        c_v1.run("search {} --revisions -r default".format(pref_rev.full_str()),
                 assert_error=True)
        self.assertIn("The remote doesn't support revisions", c_v1.out)

    def test_search_revisions_regular_results(self):
        """If I upload several revisions to a server, we can list the times"""
        server = TestServer()
        servers = OrderedDict([("default", server)])
        c_v2 = TurboTestClient(revisions_enabled=True, servers=servers)
        pref = c_v2.create(self.ref)
        c_v2.upload_all(self.ref)
        pref_rev = pref.copy_with_revs(pref.ref.revision, None)

        c_v2.run("search {} --revisions -r default".format(pref_rev.full_str()))
        # I don't want to mock here because I want to run this test against Artifactory
        self.assertIn("83c38d3b4e5f1b8450434436eec31b00 (", c_v2.out)
        self.assertIn(" UTC)", c_v2.out)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class UploadPackagesWithRevisions(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

    @parameterized.expand([(True,), (False,)])
    def test_upload_a_recipe(self, v1):
        """If we upload a package to a server:
        1. Using v1 client it will upload "0" revision to the server. The rev time is NOT updated.
        2. Using v2 client it will upload RREV revision to the server. The rev time is NOT updated.
        """
        client = self.c_v1 if v1 else self.c_v2
        pref = client.create(self.ref)
        client.upload_all(self.ref)
        revs = [r.revision for r in self.server.server_store.get_recipe_revisions(self.ref)]

        if v1:
            self.assertEqual(revs, [DEFAULT_REVISION_V1])
        else:
            self.assertEqual(revs, [pref.ref.revision])

    @parameterized.expand([(True,), (False,)])
    def test_upload_discarding_outdated_packages(self, v1):
        """If we upload all packages to a server,
           if a package doesn't belong to the current recipe:
        1. Using v1 client it will upload all the binaries as revision "0".
        2. Using v2 client it will upload only the matching packages.
        """
        conanfile = GenConanfile().with_setting("os")
        pref = self.c_v1.create(self.ref, conanfile=conanfile, args=" -s os=Windows")
        if not v1:
            self.c_v1.enable_revisions()  # Ensure we upload with v2 both revisions
        self.c_v1.upload_all(self.ref)

        # To allow creating a non-matching revision binary package
        self.c_v1.disable_revisions()
        pref2 = self.c_v1.create(self.ref, conanfile=conanfile.with_build_msg("rev2"),
                                 args=" -s os=Linux")

        # Now pref is outdated in the client, should not be uploaded with v2
        client = self.c_v1
        if not v1:
            client.enable_revisions()

        client.upload_all(self.ref)

        if not v1:
            self.assertIn("Skipping package '%s', "
                          "it doesn't belong to the current recipe revision" % pref.id, client.out)

        revs = [r.revision for r in self.server.server_store.get_recipe_revisions(self.ref)]
        if v1:
            self.assertEqual(revs, [DEFAULT_REVISION_V1])
        else:
            self.assertEqual(set(revs), set([pref.ref.revision, pref2.ref.revision]))

    @parameterized.expand([(True,), (False,)])
    def test_upload_no_overwrite_recipes(self, v1):
        """If we upload a RREV to the server and create a new RREV in the client,
        when we upload with --no-overwrite
        1. Using v1 client it will fail because it cannot overwrite.
        2. Using v2 client it will warn an upload a new revision.
        """
        client = self.c_v1 if v1 else self.c_v2
        pref = client.create(self.ref, conanfile=GenConanfile().with_setting("os"),
                             args=" -s os=Windows")
        client.upload_all(self.ref)
        pref2 = client.create(self.ref,
                              conanfile=GenConanfile().with_setting("os").with_build_msg("rev2"),
                              args=" -s os=Linux")

        if v1:
            client.upload_all(self.ref, args="--no-overwrite", assert_error=True)
            self.assertIn("Local recipe is different from the remote recipe. "
                          "Forbidden overwrite.", client.out)
        else:
            self.assertEqual(self.server.server_store.get_last_revision(self.ref)[0],
                              pref.ref.revision)
            client.upload_all(self.ref, args="--no-overwrite")
            self.assertEqual(self.server.server_store.get_last_revision(self.ref)[0],
                              pref2.ref.revision)

    @parameterized.expand([(True,), (False,)])
    def test_upload_no_overwrite_packages(self, v1):
        """If we upload a PREV to the server and create a new PREV in the client,
        when we upload with --no-overwrite
        1. Using v1 client it will fail because it cannot overwrite.
        2. Using v2 client it will warn and upload a new revision.
        """
        client = self.c_v1 if v1 else self.c_v2
        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_append({"MY_VAR": "1"}):
            pref = client.create(self.ref, conanfile=conanfile)
        client.upload_all(self.ref)

        with environment_append({"MY_VAR": "2"}):
            pref2 = client.create(self.ref, conanfile=conanfile)

        self.assertNotEqual(pref.revision, pref2.revision)

        if v1:
            client.upload_all(self.ref, args="--no-overwrite", assert_error=True)
            self.assertIn("Local package is different from the remote package. "
                          "Forbidden overwrite.", client.out)
        else:
            self.assertEqual(self.server.server_store.get_last_package_revision(pref2).revision,
                              pref.revision)
            client.upload_all(self.ref, args="--no-overwrite")
            self.assertEqual(self.server.server_store.get_last_package_revision(pref2).revision,
                              pref2.revision)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class SCMRevisions(unittest.TestCase):

    def test_auto_revision_even_without_scm_git(self):
        """Even without using the scm feature, the revision is detected from repo.
         Also while we continue working in local, the revision doesn't change, so the packages
         can be found"""
        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client = TurboTestClient()
        conanfile = GenConanfile().with_revision_mode("scm")
        commit = client.init_git_repo(files={"file.txt": "hey"}, origin_url="http://myrepo.git")
        client.create(ref, conanfile=conanfile)
        self.assertEqual(client.recipe_revision(ref), commit)

        # Change the conanfile and make another create, the revision should be the same
        client.save({"conanfile.py": str(conanfile.with_build_msg("New changes!"))})
        client.create(ref, conanfile=conanfile)
        self.assertEqual(client.recipe_revision(ref), commit)
        self.assertIn("New changes!", client.out)

    def test_auto_revision_without_commits(self):
        """If we have a repo but without commits, it has to fail when the revision_mode=scm"""
        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client = TurboTestClient()
        conanfile = GenConanfile().with_revision_mode("scm")
        client.run_command('git init .')
        client.save({"conanfile.py": str(conanfile)})
        client.run("create . {}".format(ref), assert_error=True)
        # It error, because the revision_mode is explicitly set to scm
        self.assertIn("Cannot detect revision using 'scm' mode from repository at "
                      "'{f}': Unable to get git commit from '{f}'".format(f=client.current_folder),
                      client.out)

    @pytest.mark.tool_svn
    def test_auto_revision_even_without_scm_svn(self):
        """Even without using the scm feature, the revision is detected from repo.
         Also while we continue working in local, the revision doesn't change, so the packages
         can be found"""
        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client = TurboTestClient()
        conanfile = GenConanfile().with_revision_mode("scm")
        commit = client.init_svn_repo("project",
                                      files={"file.txt": "hey", "conanfile.py": str(conanfile)})
        client.current_folder = os.path.join(client.current_folder, "project")
        client.create(ref, conanfile=conanfile)
        self.assertEqual(client.recipe_revision(ref), commit)

        # Change the conanfile and make another create, the revision should be the same
        client.save({"conanfile.py": str(conanfile.with_build_msg("New changes!"))})
        client.create(ref, conanfile=conanfile)
        self.assertEqual(client.recipe_revision(ref), commit)
        self.assertIn("New changes!", client.out)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class CapabilitiesRevisionsTest(unittest.TestCase):

    def test_server_without_revisions_capability(self):
        """If a server doesn't have the revisions capability, a modern client will still
        talk v1"""
        server = TestServer(server_capabilities=[])
        c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": server})
        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        c_v2.create(ref)
        c_v2.upload_all(ref)
        c_v2.remove_all()
        c_v2.run("install {}".format(ref))
        self.assertEqual(c_v2.recipe_revision(ref), DEFAULT_REVISION_V1)

    def test_server_with_only_v2_capability(self):
        server = TestServer(server_capabilities=[ONLY_V2])
        c_v2 = TurboTestClient(revisions_enabled=False, servers={"default": server})
        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        c_v2.create(ref)
        c_v2.upload_all(ref, remote="default", assert_error=True)
        self.assertIn("The remote at '{}' only works with revisions enabled. "
                      "Set CONAN_REVISIONS_ENABLED=1 or set 'general.revisions_enabled = 1' "
                      "at the 'conan.conf'. [Remote: default]".format(server.fake_url), c_v2.out)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class InfoRevisions(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def test_info_command_showing_revision(self, v1):
        """If I run 'conan info ref' I get information about the revision only in a v2 client"""
        server = TestServer(server_capabilities=[])
        c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": server})
        c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": server})
        ref = ConanFileReference.loads("lib/1.0@conan/testing")

        client = c_v1 if v1 else c_v2
        client.create(ref)
        client.run("info {}".format(ref))
        revision = client.recipe_revision(ref)
        if v1:
            self.assertNotIn("Revision:", client.out)
        else:
            self.assertIn("Revision: {}".format(revision), client.out)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
class ServerRevisionsIndexes(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.c_v1 = TurboTestClient(revisions_enabled=False, servers={"default": self.server})
        self.c_v2 = TurboTestClient(revisions_enabled=True, servers={"default": self.server})
        self.ref = ConanFileReference.loads("lib/1.0@conan/testing")

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

        revs = [r.revision for r in self.server.server_store.get_recipe_revisions(self.ref)]
        self.assertEqual(revs, [ref3.revision, ref2.revision, ref1.revision])
        self.assertEqual(self.server.server_store.get_last_revision(self.ref).revision,
                         ref3.revision)

        # Delete the latest from the server
        self.c_v2.run("remove {} -r default -f".format(ref3.full_str()))
        revs = [r.revision for r in self.server.server_store.get_recipe_revisions(self.ref)]
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
        with environment_append({"MY_VAR": "1"}):
            pref1 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref1).revision,
                         pref1.revision)
        with environment_append({"MY_VAR": "2"}):
            pref2 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref1).revision,
                         pref2.revision)
        with environment_append({"MY_VAR": "3"}):
            pref3 = self.c_v2.create(self.ref, conanfile=conanfile)
        server_pref3 = self.c_v2.upload_all(self.ref)
        self.assertEqual(self.server.server_store.get_last_package_revision(pref1).revision,
                         pref3.revision)

        self.assertEqual(pref1.ref.revision, pref2.ref.revision)
        self.assertEqual(pref2.ref.revision, pref3.ref.revision)
        self.assertEqual(pref3.ref.revision, server_pref3.revision)

        pref = pref1.copy_clear_prev()
        revs = [r.revision
                for r in self.server.server_store.get_package_revisions(pref)]
        self.assertEqual(revs, [pref3.revision, pref2.revision, pref1.revision])
        self.assertEqual(self.server.server_store.get_last_package_revision(pref).revision,
                         pref3.revision)

        # Delete the latest from the server
        self.c_v2.run("remove {} -p {}#{} -r default -f".format(pref3.ref.full_str(),
                                                                pref3.id, pref3.revision))
        revs = [r.revision
                for r in self.server.server_store.get_package_revisions(pref)]
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

        self.c_v2.run("remove {} -r default -f".format(ref1.full_str()))
        self.c_v2.run("remove {} -r default -f".format(ref2.full_str()))
        self.c_v2.run("remove {} -r default -f".format(ref3.full_str()))

        self.assertRaises(RecipeNotFoundException,
                          self.server.server_store.get_recipe_revisions, self.ref)

        ref4 = self.c_v2.export(self.ref, conanfile=GenConanfile().with_build_msg("I'm rev4"))
        self.c_v2.upload_all(ref4)

        revs = [r.revision for r in self.server.server_store.get_recipe_revisions(self.ref)]
        self.assertEqual(revs, [ref4.revision])

    def test_deleting_all_prevs(self):
        """
        If we delete all the package revisions in the server. There is no latest.
        If then a client uploads a RREV/PREV it is the latest
        """
        conanfile = GenConanfile().with_package_file("file", env_var="MY_VAR")
        with environment_append({"MY_VAR": "1"}):
            pref1 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        with environment_append({"MY_VAR": "2"}):
            pref2 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)
        with environment_append({"MY_VAR": "3"}):
            pref3 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)

        # Delete the package revisions (all of them have the same ref#rev and id)
        command = "remove {} -p {}#{{}} -r default -f".format(pref3.ref.full_str(), pref3.id)
        self.c_v2.run(command.format(pref3.revision))
        self.c_v2.run(command.format(pref2.revision))
        self.c_v2.run(command.format(pref1.revision))

        with environment_append({"MY_VAR": "4"}):
            pref4 = self.c_v2.create(self.ref, conanfile=conanfile)
        self.c_v2.upload_all(self.ref)

        pref = pref1.copy_clear_prev()
        revs = [r.revision
                for r in self.server.server_store.get_package_revisions(pref)]
        self.assertEqual(revs, [pref4.revision])

    def test_v1_get_always_latest(self):
        conanfile = GenConanfile()
        self.c_v1.create(self.ref, conanfile=conanfile)
        self.c_v1.upload_all(self.ref)

        pref = self.c_v2.create(self.ref, conanfile=conanfile.with_build_msg("Rev2"))
        self.c_v2.upload_all(self.ref)

        latest = self.server.server_store.get_last_revision(self.ref)
        self.assertEqual(latest.revision, pref.ref.revision)

        if get_env("CONAN_TEST_WITH_ARTIFACTORY", False):
            time.sleep(62)

        self.c_v1.create(self.ref, conanfile=conanfile.with_build_msg("Rev3"))
        self.c_v1.upload_all(self.ref)

        latest = self.server.server_store.get_last_revision(self.ref)
        self.assertEqual(latest.revision, DEFAULT_REVISION_V1)


def test_necessary_update():
    # https://github.com/conan-io/conan/issues/7235
    c = TestClient(default_server_user=True)
    save(c.cache.new_config_path, "core:allow_explicit_revision_update=True")
    c.run("config set general.revisions_enabled=True")
    c.save({"conanfile.py": GenConanfile()})
    c.run("create . pkg/0.1@")
    rrev1 = "f3367e0e7d170aa12abccb175fee5f97"
    c.run("upload * --all -c")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create . ")
    rrev2 = "27ec09effe18a84f465dbc350e496335"
    c.run("upload * --all -c")

    c.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1#{}".format(rrev1))})
    c.run("install .")
    assert rrev1 in c.out
    c.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1#{}".format(rrev2))})
    c.run("install .")
    assert rrev2 in c.out


def test_touching_other_server():
    # https://github.com/conan-io/conan/issues/9333
    servers = OrderedDict([("remote1", TestServer()),
                           ("remote2", None)])  # None server will crash if touched
    c = TestClient(servers=servers, users={"remote1": [("conan", "password")]})
    c.run("config set general.revisions_enabled=True")
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . pkg/0.1@conan/channel -s os=Windows")
    c.run("upload * --all -c -r=remote1")
    c.run("remove * -f")

    # This is OK, binary found
    c.run("install pkg/0.1@conan/channel -r=remote1 -s os=Windows")
    c.run("install pkg/0.1@conan/channel -r=remote1 -s os=Linux", assert_error=True)
    assert "ERROR: Missing binary: pkg/0.1@conan/channel" in c.out
