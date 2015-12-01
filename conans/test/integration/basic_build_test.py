import unittest
from conans.test.tools import TestClient
import os
from conans.paths import CONANINFO
import platform
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.util.files import load
from conans.model.info import ConanInfo
import time


@attr("slow")
class BasicBuildTest(unittest.TestCase):

    def complete_build_flow_test(self):
        """In local user folder"""
        files = cpp_hello_conan_files("Hello0", "0.1")
        client = TestClient()
        client.save(files)
        command = "say_hello" if platform.system() == "Windows" else "./say_hello"

        for install, lang, static in [("install", 0, True),
                                      ("install -o language=1", 1, True),
                                      ("install -o language=1 -o static=False", 1, False),
                                      ("install -o static=False", 0, False)]:
            client.run(install)
            time.sleep(1)  # necessary so the conaninfo.txt is flushed to disc
            client.run('build')
            client.runner(command, client.current_folder)
            msg = "Hello" if lang == 0 else "Hola"
            self.assertIn("%s Hello0" % msg, client.user_io.out)
            conan_info_path = os.path.join(client.current_folder, CONANINFO)
            conan_info = ConanInfo.loads(load(conan_info_path))
            self.assertTrue(conan_info.full_options.language == lang)
            if static:
                self.assertTrue(conan_info.full_options.static)
            else:
                self.assertFalse(conan_info.full_options.static)
