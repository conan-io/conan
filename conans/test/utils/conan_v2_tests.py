import os
import unittest

from conans.client.conf import get_default_settings_yml
from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient
from conans.util.conan_v2_mode import CONAN_V2_MODE_ENVVAR
from conans.client.cache.cache import CONAN_SETTINGS


class ConanV2ModeTestCase(unittest.TestCase):

    @staticmethod
    def get_client(*args, **kwargs):
        # TODO: Initialize with the default behavior for Conan v2
        t = TestClient(*args, **kwargs)
        return t

    def run(self, *args, **kwargs):
        with environment_append({CONAN_V2_MODE_ENVVAR: "1"}):
            super(ConanV2ModeTestCase, self).run(*args, **kwargs)
