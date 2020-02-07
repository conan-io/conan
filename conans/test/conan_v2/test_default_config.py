import textwrap

import six

from conans.client import settings_preprocessor
from conans.client.conf import default_settings_yml
from conans.errors import ConanV2Exception
from conans.model.settings import Settings
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class DefaultConfigTestCase(ConanV2ModeTestCase):
    def test_revisions_enabled(self):
        t = self.get_client()
        t.run('config get general.revisions_enabled')
        self.assertEqual(t.out, "1")
