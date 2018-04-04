import unittest

from conans.test.utils.tools import TestServer, TestClient


class RevisionsTest(unittest.TestCase):

    def _export_package(self, client, name, version, rev_number, requires=None):
        req = "requires='%s'" % requires if requires else ""
        conanfile = '''from conans import ConanFile
class MyConanfile(ConanFile):
    name = "%s"
    version = "%s"
    _revision_ = %s
    %s
''' % (name, version, rev_number, req)
        client.save({"conanfile.py": conanfile})
        client.run("export . user/channel")

    def setUp(self):
        self.test_server = TestServer()  # exported users and passwords
        self.client = TestClient(servers={"default": self.test_server})

        self._export_package(self.client, "AA", "1.0", 1)
        self._export_package(self.client, "AA", "1.0", 2)
        self._export_package(self.client, "AA", "1.0", 3)

        self._export_package(self.client, "BB", "1.0", 1, "AA/1.0@user/channel")
        self._export_package(self.client, "BB", "1.0", 2, "AA/1.0@user/channel")
        self._export_package(self.client, "CC", "1.0", 3, "AA/1.0@user/channel")

    def test_depend_on_revision(self):
        pass

    def test_no_export_restrictions(self):
        pass

    def test_no_upload_restrictions(self):
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
        pass# by revision, global

    def remove_remote(self):
        pass #


