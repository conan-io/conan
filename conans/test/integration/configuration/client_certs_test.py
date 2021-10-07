import os
import unittest

from conans.client import tools
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


class ClientCertsTest(unittest.TestCase):
    class MyHttpRequester(object):
        def __init__(self, *args, **kwargs):
            pass

        def get(self, _, **kwargs):
            return kwargs.get("cert", None)

    def test_pic_client_certs(self):
        client = TestClient(requester_class=self.MyHttpRequester)
        self.assertIsNone(client.requester.get("url"))

        config = client.cache.config
        tools.save(config.client_cert_path, "Fake cert")

        self.assertEqual(client.requester.get("url"), client.cache.config.client_cert_path)

        tools.save(config.client_cert_path, "Fake cert")
        tools.save(config.client_cert_key_path, "Fake key")
        self.assertEqual(client.requester.get("url"), (config.client_cert_path,
                                                       config.client_cert_key_path))

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(config.cacert_path))

    def test_pic_custom_path_client_certs(self):
        folder = temp_folder()
        mycert_path = os.path.join(folder, "mycert.crt")
        mykey_path = os.path.join(folder, "mycert.key")
        save(mycert_path, "Fake Cert")
        save(mykey_path, "Fake Key")

        client = TestClient(requester_class=self.MyHttpRequester)
        client.run('config set general.client_cert_path="%s"' % mycert_path)
        client.run('config set general.client_cert_key_path="%s"' % mykey_path)

        self.assertEqual(client.requester.get("url"), (mycert_path, mykey_path))

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(client.cache.config.cacert_path))
