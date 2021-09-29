import os
import textwrap
import unittest

from requests import Response

from conans.client import tools
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestRequester
from conans.util.files import save


conanfile = textwrap.dedent("""
    from conans import ConanFile
    from conans import tools

    class Pkg(ConanFile):
        settings = "os", "compiler"

        def source(self):
            tools.download("http://foo.bar/file", "filename.txt")
    """)


class MyHttpRequester(TestRequester):

    def get(self, _, **kwargs):
        resp = Response()
        # resp._content = b'{"results": []}'
        resp.status_code = 200
        resp._content = b''
        # This will be captured in the TestClient.out too
        print("KWARGS auth: {}".format(kwargs["auth"]))
        print("KWARGS verify: {}".format(kwargs["verify"]))
        print("KWARGS cert: {}".format(kwargs["cert"]))
        return resp


class ClientCertsTest(unittest.TestCase):

    def test_pic_client_certs(self):

        client = TestClient(requester_class=MyHttpRequester)
        client.save({"conanfile.py": conanfile})
        client.run("create . foo/1.0@")
        assert "KWARGS auth: None" in client.out

        config = client.cache.config
        tools.save(config.client_cert_path, "Fake cert")
        tools.save(config.client_cert_key_path, "Fake key")

        client.run("create . foo/1.0@")
        assert "KWARGS cert: ('{}', '{}')".format(config.client_cert_path,
                                                  config.client_cert_key_path) in client.out

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(config.cacert_path))

    def test_pic_custom_path_client_certs(self):
        folder = temp_folder()
        mycert_path = os.path.join(folder, "mycert.crt")
        mykey_path = os.path.join(folder, "mycert.key")
        save(mycert_path, "Fake Cert")
        save(mykey_path, "Fake Key")

        client = TestClient(requester_class=MyHttpRequester)
        client.run('config set general.client_cert_path="%s"' % mycert_path)
        client.run('config set general.client_cert_key_path="%s"' % mykey_path)

        client.save({"conanfile.py": conanfile})
        client.run("create . foo/1.0@")
        assert "KWARGS cert: ('{}', '{}')".format(mycert_path, mykey_path) in client.out

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(client.cache.config.cacert_path))
