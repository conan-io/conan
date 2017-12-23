import unittest
from conans.test.utils.tools import TestClient
import os
from conans.paths import CONANINFO
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.util.files import load
from conans.model.info import ConanInfo
import platform
from conans.util.log import logger


@attr("slow")
class BasicBuildTest(unittest.TestCase):

    def build_cmake_test(self):
        for cmd, lang, static, pure_c in [("install .", 0, True, True),
                                          ("install . -o language=1 -o static=False", 1, False, False)]:
            build(self, cmd, static, pure_c, use_cmake=True, lang=lang)

    def build_default_test(self):
        "build default (gcc in nix, VS in win)"
        if platform.system() == "SunOS":
            return  # If is using sun-cc the gcc generator doesn't work

        for cmd, lang, static, pure_c in [("install .", 0, True, True),
                                          ("install . -o language=1 -o static=False -g txt", 1, False, False)]:
            build(self, cmd, static, pure_c, use_cmake=False, lang=lang)


def build(tester, cmd, static, pure_c, use_cmake, lang):
    client = TestClient()
    dll_export = client.default_compiler_visual_studio and not static
    files = cpp_hello_conan_files("Hello0", "0.1", dll_export=dll_export,
                                  pure_c=pure_c, use_cmake=use_cmake)

    client.save(files)
    client.run(cmd)
    client.run('build .')
    ld_path = ("LD_LIBRARY_PATH=`pwd`"
               if not static and not platform.system() == "Windows" else "")
    if platform.system() == "Darwin":
        ld_path += ' DYLD_LIBRARY_PATH="%s"' % os.path.join(client.current_folder, 'lib')
    command = os.sep.join([".", "bin", "say_hello"])
    client.runner("%s %s" % (ld_path, command), cwd=client.current_folder)
    msg = "Hello" if lang == 0 else "Hola"
    tester.assertIn("%s Hello0" % msg, client.user_io.out)
    conan_info_path = os.path.join(client.current_folder, CONANINFO)
    conan_info = ConanInfo.loads(load(conan_info_path))
    tester.assertTrue(conan_info.full_options.language == lang)
    if static:
        tester.assertTrue(conan_info.full_options.static)
    else:
        tester.assertFalse(conan_info.full_options.static)