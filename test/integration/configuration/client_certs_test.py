import os
import textwrap
import unittest

from requests import Response

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, TestRequester
from conans.util.files import save


conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.files import download

    class Pkg(ConanFile):
        settings = "os", "compiler"

        def source(self):
            download(self, "http://foo.bar/file", "filename.txt")
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

    def test_pic_custom_path_client_certs(self):
        folder = temp_folder()
        mycert_path = os.path.join(folder, "mycert.crt").replace("\\", '/')
        mykey_path = os.path.join(folder, "mycert.key").replace("\\", '/')
        save(mycert_path, "Fake Cert")
        save(mykey_path, "Fake Key")

        client = TestClient(requester_class=MyHttpRequester)
        conan_conf = textwrap.dedent("""
                                    core.net.http:client_cert= ("{}", "{}")
                                """.format(mycert_path, mykey_path))
        client.save_home({"global.conf": conan_conf})
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "KWARGS cert: ('{}', '{}')".format(mycert_path, mykey_path) in client.out
