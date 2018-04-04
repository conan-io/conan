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
                                                         ("BB/1.0@user/channel", "private_user")])
        self.client = TestClient(servers={"default": self.test_server})

    def test_depend_on_revision(self):
        self._create_package(self.client, "AA", "1.0", 1)
        self._create_package(self.client, "AA", "1.0", 2)
        self._create_package(self.client, "BB", "1.0", 1, "AA/1.0@user/channel#2")
        self.assertIn("I AM AA#2", self.client.out)
        self.assertIn("I AM BB#1", self.client.out)

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
        pass

    def test_resolving_local_cache(self):
        pass


    def test_resolving_remote(self):
        pass


    def update_from_server_test(self):
        # if global ref, => updated, if don't dont.
        pass

    def search_local(self):
        pass

    def search_remote(self):
        pass

    def remove_local(self):
        pass # by revision, global

    def remove_remote(self):
        pass

    def registry_associate_reference(self):
        pass
        # client 1:
        # Upload AA#1 to remote 1
        # client 2:
        # Upload AA#2 to remote 2
        # client 1:
        # install AA#2 should fail, already associated to remote 1

