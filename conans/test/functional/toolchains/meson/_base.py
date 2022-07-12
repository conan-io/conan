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

    @property
    def _settings(self):
        settings_macosx = {"compiler": "apple-clang",
                           "compiler.libcxx": "libc++",
                           "compiler.version": "12.0",
                           "arch": "x86_64",
                           "build_type": "Release"}

        settings_windows = {"compiler": "Visual Studio",
                            "compiler.version": "15",
                            "compiler.runtime": "MD",
                            "arch": "x86_64",
                            "build_type": "Release"}

        settings_linux = {"compiler": "gcc",
                          "compiler.version": "5",
                          "compiler.libcxx": "libstdc++",
                          "arch": "x86_64",
                          "build_type": "Release"}

        return {"Darwin": settings_macosx,
                "Windows": settings_windows,
                "Linux": settings_linux}.get(platform.system())

    @property
    def _settings_str(self):
        return " ".join('-s %s="%s"' % (k, v) for k, v in self._settings.items() if v)

    def _check_binary(self):
        if platform.system() == "Darwin":
            self.assertIn("main __x86_64__ defined", self.t.out)
            self.assertIn("main __apple_build_version__", self.t.out)
            self.assertIn("main __clang_major__12", self.t.out)
            # TODO: check why __clang_minor__ seems to be not defined in XCode 12
            # commented while migrating to XCode12 CI
            # self.assertIn("main __clang_minor__0", self.t.out)
        elif platform.system() == "Windows":
            self.assertIn("main _M_X64 defined", self.t.out)
            self.assertIn("main _MSC_VER19", self.t.out)
            self.assertIn("main _MSVC_LANG2014", self.t.out)
        elif platform.system() == "Linux":
            self.assertIn("main __x86_64__ defined", self.t.out)
            self.assertIn("main __GNUC__5", self.t.out)
