import os
import unittest

from conans.client import tools
from conans.client.cache.cache import ClientCache
from conans.client.rest.conan_requester import ConanRequester
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput


class ClientCertsTest(unittest.TestCase):

    def pic_client_certs_test(self):
        class MyRequester(object):
            def get(self, _, **kwargs):
                return kwargs.get("cert", None)

        cache = ClientCache(temp_folder(), TestBufferConanOutput())
        requester = ConanRequester(cache, requester=MyRequester())
        self.assertIsNone(requester.get("url"))

        tools.save(cache.client_cert_path, "Fake cert")
        requester = ConanRequester(cache, requester=MyRequester())
        self.assertEqual(requester.get("url"), cache.client_cert_path)

        tools.save(cache.client_cert_path, "Fake cert")
        tools.save(cache.client_cert_key_path, "Fake key")
        requester = ConanRequester(cache, requester=MyRequester())
        self.assertEqual(requester.get("url"), (cache.client_cert_path,
                                                cache.client_cert_key_path))

        # assert that the cacert file is created
        self.assertTrue(os.path.exists(cache.cacert_path))
