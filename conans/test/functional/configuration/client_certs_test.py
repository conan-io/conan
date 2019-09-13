import os
import unittest

from conans.client import tools
from conans.test.utils.tools import TestClient


class ClientCertsTest(unittest.TestCase):

    def pic_client_certs_test(self):

        class MyRequester(object):

            def __init__(*args, **kwargs):
                pass

            def get(self, _, **kwargs):
                return kwargs.get("cert", None)

        client = TestClient(requester_class=MyRequester)
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
