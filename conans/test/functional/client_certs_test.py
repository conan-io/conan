import os
import unittest

from conans import tools
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

        tools.save(client.client_cache.client_cert_path, "Fake cert")
        client.init_dynamic_vars()

        self.assertEquals(client.requester.get("url"), client.client_cache.client_cert_path)

        tools.save(client.client_cache.client_cert_path, "Fake cert")
        tools.save(client.client_cache.client_cert_key_path, "Fake key")
        client.init_dynamic_vars()
        self.assertEquals(client.requester.get("url"), (client.client_cache.client_cert_path,
                                                        client.client_cache.client_cert_key_path))

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(client.client_cache.cacert_path))
