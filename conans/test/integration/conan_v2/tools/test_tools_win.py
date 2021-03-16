import six

from conans import tools
from conans.errors import ConanV2Exception
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class ToolsWinTestCase(ConanV2ModeTestCase):
    def test_msvc_build_command(self):
        with six.assertRaisesRegex(self, ConanV2Exception, "Conan v2 incompatible: 'tools.msvc_build_command' is deprecated"):
            tools.msvc_build_command(settings=None, sln_path=None)

    def test_build_sln_command(self):
        with six.assertRaisesRegex(self, ConanV2Exception, "Conan v2 incompatible: 'tools.build_sln_command' is deprecated"):
            tools.build_sln_command(settings=None, sln_path=None)
