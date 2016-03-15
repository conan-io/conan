import unittest
from conans.test.tools import TestClient
import os
from conans.paths import CONANINFO
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.util.files import load
from conans.model.info import ConanInfo
import time


@attr("slow")
class BasicBuildTest(unittest.TestCase):

    def complete_build_flow_test(self):
        """In local user folder"""
        client = TestClient()
        command = os.sep.join([".", "bin", "say_hello"])

        for pure_c in (False, True):
            for install, lang, static in [("install", 0, True),
                                          ("install -o language=1", 1, True),
                                          ("install -o language=1 -o static=False", 1, False),
                                          ("install -o static=False", 0, False)]:
                dll_export = client.default_compiler_visual_studio and not static
                files = cpp_hello_conan_files("Hello0", "0.1", dll_export=dll_export,
                                              pure_c=pure_c)
                client.save(files, clean_first=True)
                client.run(install)
                time.sleep(1)  # necessary so the conaninfo.txt is flushed to disc
                client.run('build')
                client.runner(command, cwd=client.current_folder)
                msg = "Hello" if lang == 0 else "Hola"
                self.assertIn("%s Hello0" % msg, client.user_io.out)
                conan_info_path = os.path.join(client.current_folder, CONANINFO)
                conan_info = ConanInfo.loads(load(conan_info_path))
                self.assertTrue(conan_info.full_options.language == lang)
                if static:
                    self.assertTrue(conan_info.full_options.static)
                else:
                    self.assertFalse(conan_info.full_options.static)
