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
        interpreter_arch = platform.machine()
        if interpreter_arch in ["x86_64", "AMD64"]:
            host_arch = "x86_64"
        elif interpreter_arch in ["arm64", "aarch64", "ARM64"]:
            host_arch = "armv8"
        else:
            host_ach = interpreter_arch
        settings_macosx = {"compiler": "apple-clang",
                           "compiler.libcxx": "libc++",
                           "compiler.version": "13",
                           "arch": host_arch,
                           "build_type": "Release"}

        settings_windows = {"compiler": "Visual Studio",
                            "compiler.version": "15",
                            "compiler.runtime": "MD",
                            "arch": host_arch,
                            "build_type": "Release"}

        settings_linux = {"compiler": "gcc",
                          "compiler.version": "5",
                          "compiler.libcxx": "libstdc++",
                          "arch": host_arch,
                          "build_type": "Release"}

        return {"Darwin": settings_macosx,
                "Windows": settings_windows,
                "Linux": settings_linux}.get(platform.system())

    @property
    def _settings_str(self):
        return " ".join('-s %s="%s"' % (k, v) for k, v in self._settings.items() if v)

    def _check_binary(self):
        # FIXME: Some values are hardcoded to match the CI setup
        host_arch =  self.t.get_default_host_profile().settings['arch']
        arch_macro = {
            "gcc": {"armv8": "__aarch64__", "x86_64": "__x86_64__"},
            "msvc": {"armv8": "_M_ARM64", "x86_64": "_M_X64"}
        }
        if platform.system() == "Darwin":
            self.assertIn(f"main {arch_macro['gcc'][host_arch]} defined", self.t.out)
            self.assertIn("main __apple_build_version__", self.t.out)
            self.assertIn("main __clang_major__13", self.t.out)
            # TODO: check why __clang_minor__ seems to be not defined in XCode 12
            # commented while migrating to XCode12 CI
            # self.assertIn("main __clang_minor__0", self.t.out)
        elif platform.system() == "Windows":
            self.assertIn(f"main {arch_macro['msvc'][host_arch]} defined", self.t.out)
            self.assertIn("main _MSC_VER19", self.t.out)
            self.assertIn("main _MSVC_LANG2014", self.t.out)
        elif platform.system() == "Linux":
            self.assertIn(f"main {arch_macro['gcc'][host_arch]} defined", self.t.out)
            self.assertIn("main __GNUC__5", self.t.out)
