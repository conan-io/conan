import unittest

from conans.test.utils.tools import TestServer, TestClient


class RevisionsTest(unittest.TestCase):

    conanfile = '''from conans import ConanFile
class MyConanfile(ConanFile):
    name = "%s"
    version = "%s"
    _revision_ = %s
    %s

    def package_info(self):
        self.output.warn("I AM "+ str(self.name) + "#" + str(self._revision_))
'''

    def _create_package(self, client, name, version, rev_number, requires=None):
        req = "requires='%s'" % requires if requires else ""
        client.save({"conanfile.py": self.conanfile % (name, version, rev_number, req)})
        client.run("create . user/channel")

    def setUp(self):
        self.test_server = TestServer(write_permissions=[("AA/1.0@user/channel", "private_user"),
                                                         ("AA/1.2@user/channel", "private_user"),
                                                         ("AA/1.3@user/channel", "private_user"),
                                                         ("AA/1.4@user/channel", "private_user"),
                                                         ("BB/1.0@user/channel", "private_user")])
        self.client = TestClient(servers={"default": self.test_server})

    def test_depend_on_revision(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 1, "AA/1.0@user/channel#2")
        self.assertIn("I AM AA#2", self.client.out)
        self.assertIn("I AM BB#1", self.client.out)

    def test_resolve_from_local_cache(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        # Install the latest
        self.client.run("install AA/1.0@user/channel")
        self.assertIn("I AM AA#2", self.client.out)
        # Install the specified revision
        self.client.run("install AA/1.0@user/channel#1")
        self.assertIn("I AM AA#1", self.client.out)
        # Now with conanfile.txt
        self.client.save({"conanfile.txt": "[requires]\nAA/1.0@user/channel#1#comment"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("I AM AA#1", self.client.out)

    def test_export_restrictions(self):
        # We can export later a lower version
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "AA", "1.0", 1)

        # We cannot export a non number one
        self.client.save({"conanfile.py": self.conanfile % ("lib", "1.0", '"paquito"', None)})
        error = self.client.run("create . user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Specify an integer revision", self.client.out)

        # We can export twice the same version
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "AA", "1.0", 2)

    def test_upload_restrictions(self):
        # We can override a revision, it depends on the server permissions or --no-overwrite only
        # and we can upload a revision with permission to upload only the reference
        self._create_package(self.client, "AA", "1.0", 2)
        self.client.run('upload "AA*" -r default -c')
        self._create_package(self.client, "AA", "1.0", 2)
        self.client.run('upload "AA*" -r default -c')

    def test_circular_dep_between_revisions(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 1, "AA/1.0@user/channel#2")
        with self.assertRaises(Exception):
            self._create_package(self.client, "AA", "1.0", 3, "BB/1.0@user/channel#1")
        self.assertIn("Requirement AA/1.0@user/channel#2 conflicts with "
                      "already defined AA/1.0@user/channel#3", self.client.out)

    def test_resolving_latest(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 19, "AA/1.0@user/channel")
        # Resolve locally
        self.client.save({"conanfile.txt": "[requires]\nBB/1.0@user/channel"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("I AM AA#2", self.client.out)
        self.assertIn("I AM BB#19", self.client.out)
        # Upload and resolve remotely
        self.client.run('upload "*" -c --all')
        self.client.run('remove "*" -f')
        self.client.run("install .")
        self.assertIn("BB/1.0@user/channel: Not found in local cache", self.client.out)
        self.assertIn("I AM AA#2", self.client.out)
        self.assertIn("I AM BB#19", self.client.out)

    def update_from_server_test(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 19, "AA/1.0@user/channel")
        self.client.run('upload "*" -c --all')
        self.client.save({"conanfile.txt": "[requires]\nBB/1.0@user/channel"}, clean_first=True)
        self.client.run("install .")

        # We upload a new revision of AA with other client
        client2 = TestClient(servers={"default": self.test_server})
        self._create_package(client2, "AA", "1.0", 45)
        client2.run('upload "*" -c --all')
        self.assertIn("Uploaded conan recipe 'AA/1.0@user/channel#45'", client2.out)

        # We install with the previous client, nothing happens
        self.client.run("install .")
        self.assertIn("Already installed!", self.client.out)
        self.assertIn("I AM AA#2", self.client.out)

        # We install with --update, it finds AA#45
        self.client.run("install . --update")
        self.assertIn("I AM AA#45", self.client.out)

        # Now we override a revision in the remote and update, it should retrieve the newest one
        a_conanfile = self.conanfile % ("AA", "1.0", "45", "")
        a_conanfile = a_conanfile.replace("I AM", "I AM A NEW")
        client2.save({"conanfile.py": a_conanfile}, clean_first=True)
        client2.run("create . user/channel")
        client2.run('upload "*" -c --all')

        self.client.run("install . --update")
        self.assertIn("I AM A NEW AA#45", self.client.out)

        # If we require a concrete revision it won't upgrade it
        self.client.save({"conanfile.txt": "[requires]\nAA/1.0@user/channel#1"}, clean_first=True)
        self.client.run("install . --update")
        self.assertIn("I AM AA#1", self.client.out)

    def test_info_update(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 19, "AA/1.0@user/channel")
        self.client.run('upload "*" -c --all')
        self.client.save({"conanfile.txt": "[requires]\nBB/1.0@user/channel"}, clean_first=True)
        self.client.run("install .")

        # We upload a new revision of AA with other client
        client2 = TestClient(servers={"default": self.test_server})
        self._create_package(client2, "AA", "1.0", 45)
        client2.run('upload "*" -c --all')
        self.assertIn("Uploaded conan recipe 'AA/1.0@user/channel#45'", client2.out)

        # We try the info update
        self.client.run('info . --update')
        self.assertIn("Updates: There is a newer version (default)", self.client.out)

        self.client.run("install . --update")

        # We try the info update
        self.client.run('info . --update')
        self.assertNotIn("Updates: There is a newer version (default)", self.client.out)

    def search_test(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 19, "AA/1.0@user/channel")
        self.client.run('search "*"')
        self.assertIn("AA/1.0@user/channel#1", self.client.out)
        self.assertIn("AA/1.0@user/channel#2", self.client.out)
        self.assertIn("BB/1.0@user/channel#19", self.client.out)

        self.client.run('upload "*" -c --all')
        self.client.run('remove "*" -f')

        self.client.run('search "A*" -r default')
        self.assertIn("AA/1.0@user/channel#1", self.client.out)
        self.assertIn("AA/1.0@user/channel#2", self.client.out)
        self.assertNotIn("BB/1.0@user/channel#19", self.client.out)

    def remove_test(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 19, "AA/1.0@user/channel")
        self.client.run('upload "*" -c --all')  # Upload for later testing
        self.client.run('remove AA/1.0@user/channel#1 -f')
        self.client.run('search "A*"')
        self.assertNotIn("AA/1.0@user/channel#1", self.client.out)
        self.assertIn("AA/1.0@user/channel#2", self.client.out)

        self.client.run('remove AA/1.0@user/channel#2 -f')
        self.client.run('search "A*"')
        self.assertIn("There are no packages matching the 'A*' pattern", self.client.out)

        # Removing the reference without revision DO NOT remove any revision
        self._create_package(self.client, "AA", "1.0", 1)
        self.client.run('remove AA/1.0@user/channel -f')
        self.assertIn("No package recipe matches 'AA/1.0@user/channel'", self.client.out)

        # Test remote remove
        self.client.run('remove AA/1.0@user/channel#1 -f -r default')
        self.client.run('search "A*" -r default')
        self.assertNotIn("AA/1.0@user/channel#1", self.client.out)
        self.assertIn("AA/1.0@user/channel#2", self.client.out)

        self.client.run('remove AA/1.0@user/channel#2 -f -r default')
        self.client.run('search "A*" -r default')
        self.assertIn("There are no packages matching the 'A*' pattern", self.client.out)

    def version_ranges_revisions_test(self):
        # Resolve to the latest without specifying revision
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "AA", "1.4", 1)
        self._create_package(self.client, "AA", "1.4", 2)
        self._create_package(self.client, "BB", "1.0", 19, "AA/[>1.0, <2.0]@user/channel")
        self.assertIn("WARN: I AM AA#2", self.client.out)
        self.assertIn("WARN: I AM BB#19", self.client.out)

        # Now test remotely
        self.client.run('upload "AA*" -c --all')
        self.client.run('remove "AA*" -f')
        self._create_package(self.client, "BB", "1.0", 19, "AA/[>1.0, <2.0]@user/channel")

