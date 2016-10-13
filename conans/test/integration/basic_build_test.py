import unittest
from conans.test.tools import TestClient
import os
from conans.paths import CONANINFO
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.util.files import load
from conans.model.info import ConanInfo
import time
import platform
from conans.util.log import logger


@attr("slow")
class BasicBuildTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.command = os.sep.join([".", "bin", "say_hello"])

    def _build(self, cmd, static, pure_c, use_cmake, lang):
        dll_export = self.client.default_compiler_visual_studio and not static
        files = cpp_hello_conan_files("Hello0", "0.1", dll_export=dll_export,
                                      pure_c=pure_c, use_cmake=use_cmake)
        self.client.save(files, clean_first=True)
        self.client.run(cmd)
        time.sleep(1)  # necessary so the conaninfo.txt is flushed to disc
        self.client.run('build')
        ld_path = ("LD_LIBRARY_PATH=$(pwd)"
                   if not static and not platform.system() == "Windows" else "")
        self.client.runner("%s %s" % (ld_path, self.command), cwd=self.client.current_folder)
        msg = "Hello" if lang == 0 else "Hola"
        self.assertIn("%s Hello0" % msg, self.client.user_io.out)
        conan_info_path = os.path.join(self.client.current_folder, CONANINFO)
        conan_info = ConanInfo.loads(load(conan_info_path))
        self.assertTrue(conan_info.full_options.language == lang)
        if static:
            self.assertTrue(conan_info.full_options.static)
        else:
            self.assertFalse(conan_info.full_options.static)

    def build_cmake_test(self):
        for pure_c in (False, True):
            for cmd, lang, static in [("install", 0, True),
                                      ("install -o language=1", 1, True),
                                      ("install -o language=1 -o static=False", 1, False),
                                      ("install -o static=False", 0, False)]:
                self._build(cmd, static, pure_c, use_cmake=True, lang=lang)

    def build_default_test(self):
        "build default (gcc in nix, VS in win)"
        for pure_c in (False, True):
            for cmd, lang, static in [("install", 0, True),
                                      ("install -o language=1", 1, True),
                                      ("install -o language=1 -o static=False", 1, False),
                                      ("install -o static=False", 0, False)]:
                self._build(cmd, static, pure_c, use_cmake=False, lang=lang)

    def build_mingw_test(self):
        if platform.system() != "Windows":
            return
        not_env = os.system("g++ --version > nul")
        if not_env != 0:
            logger.error("This platform does not support G++ command")
            return
        install = "install -s compiler=gcc -s compiler.libcxx=libstdc++ -s compiler.version=4.9"
        for pure_c in (False, True):
            for cmd, lang, static in [(install, 0, True),
                                      (install + " -o language=1", 1, True),
                                      (install + " -o language=1 -o static=False", 1, False),
                                      (install + " -o static=False", 0, False)]:
                self._build(cmd, static, pure_c, use_cmake=False, lang=lang)
