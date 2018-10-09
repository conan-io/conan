import unittest
from conans.test.utils.tools import TestServer, TestClient, TestRequester
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
import os
from conans.util.files import save


class BrokenDownloadTest(unittest.TestCase):

    def basic_test(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files()
        client.save(files)
        client.run("export . lasote/stable")
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.export(ref)))
        client.run("upload Hello/0.1@lasote/stable")
        client.run("remove Hello/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))
        path = server.test_server.server_store.export(ref)
        tgz = os.path.join(path, "conan_export.tgz")
        save(tgz, "contents")  # dummy content to break it, so the download decompress will fail
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("ERROR: Error while downloading/extracting files to", client.user_io.out)
        self.assertFalse(os.path.exists(client.paths.export(ref)))

    def client_retries_test(self):
        server = TestServer()
        servers = {"default": server}
        conanfile = """from conans import ConanFile

class ConanFileToolsTest(ConanFile):
    pass
"""
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile})
        client.run("create . lib/1.0@lasote/stable")
        client.run("upload lib/1.0@lasote/stable -c --all")

        class DownloadFilesBrokenRequester(TestRequester):

            def __init__(self, *args, **kwargs):
                self.first_fail = False
                super(DownloadFilesBrokenRequester, self).__init__(*args, **kwargs)

            def get(self, url, **kwargs):
                if "conaninfo.txt" in url and not self.first_fail:
                    self.first_fail = True
                    raise ConnectionError("Fake connection error exception")
                else:
                    return super(DownloadFilesBrokenRequester, self).get(url, **kwargs)

        client2 = TestClient(servers=servers,
                             users={"default": [("lasote", "mypass")]},
                             requester_class=DownloadFilesBrokenRequester)
        client2.run("install lib/1.0@lasote/stable")
        self.assertEqual(1, str(client2.out).count("Waiting 0 seconds to retry..."))
