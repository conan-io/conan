import platform
import sys
import unittest

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() not in ("Darwin", "Windows", "Linux"),
                    reason="Not tested for not mainstream boring operating systems")
class TestMesonBase(unittest.TestCase):
    def setUp(self):
        self.t = TestClient()

    def _check_binary(self):
        # FIXME: This is hardcoded for CI
        if platform.system() == "Darwin":
            self.assertIn("main __x86_64__ defined", self.t.out)
            self.assertIn("main __apple_build_version__", self.t.out)
            self.assertIn("main __clang_major__13", self.t.out)
            # TODO: check why __clang_minor__ seems to be not defined in XCode 12
            # commented while migrating to XCode12 CI
            # self.assertIn("main __clang_minor__0", self.t.out)
        elif platform.system() == "Windows":
            self.assertIn("main _M_X64 defined", self.t.out)
            self.assertIn("main _MSC_VER19", self.t.out)
            self.assertIn("main _MSVC_LANG2014", self.t.out)
        elif platform.system() == "Linux":
            self.assertIn("main __x86_64__ defined", self.t.out)
            self.assertIn("main __GNUC__9", self.t.out)
