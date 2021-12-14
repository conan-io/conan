import os
import textwrap
import unittest

import pytest
from requests import Response

from conans.client import tools
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestRequester
from conans.util.files import save


conanfile = textwrap.dedent("""
    from conans import ConanFile
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

    @pytest.mark.xfail(reason="Legacy conan.conf configuration deprecated")
    def test_pic_client_certs(self):
        # FIXME: We need a way to reference the current cache location in "global.conf"
        # TODO: Discuss if dropping a "xxx.cert" file inthe cache would work as it is the default
        client = TestClient(requester_class=MyHttpRequester)
        client.save({"conanfile.py": conanfile})
        client.run("create . foo/1.0@")

        assert "KWARGS auth: None" in client.out

        config = client.cache.config
        tools.save(config.client_cert_path, "Fake cert")
        tools.save(config.client_cert_key_path, "Fake key")

        client.run("create . foo/1.0@")
        assert "KWARGS cert: ('{}', '{}')".format(config.client_cert_path,
                                                  config.client_cert_key_path).replace("\\", '\\\\') in client.out

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(config.cacert_path))

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
        client.save({"global.conf": conan_conf}, path=client.cache.cache_folder)
        client.save({"conanfile.py": conanfile})
        client.run("create . foo/1.0@")
        assert "KWARGS cert: ('{}', '{}')".format(mycert_path, mykey_path) in client.out
