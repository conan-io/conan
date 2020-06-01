# coding=utf-8

import os
import platform
import re
import textwrap
import unittest

from jinja2 import Template
from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class


_running_ci = 'JOB_NAME' in os.environ


@attr("toolchain")
class AdjustAutoTestCase(unittest.TestCase):
    """
        Check that it works adjusting values from the toolchain file
    """

    @unittest.skipIf(platform.system() != "Darwin", "Only MacOS")
    def test_ccxx_flags_macos(self):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_CXX_FLAGS: -m64 -stdlib=libc++", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_DEBUG: -g", configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_RELEASE: -O3 -DNDEBUG", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_DEBUG: -g", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_RELEASE: -O3 -DNDEBUG", configure_out)

        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: ", configure_out)

        self.assertEqual("-m64 -stdlib=libc++", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
        self.assertEqual("-m64", cmake_cache["CMAKE_C_FLAGS:STRING"])
        self.assertEqual("-m64", cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("-g", cmake_cache["CMAKE_CXX_FLAGS_DEBUG:STRING"])
        self.assertEqual("-O3 -DNDEBUG", cmake_cache["CMAKE_CXX_FLAGS_RELEASE:STRING"])
        self.assertEqual("-g", cmake_cache["CMAKE_C_FLAGS_DEBUG:STRING"])
        self.assertEqual("-O3 -DNDEBUG", cmake_cache["CMAKE_C_FLAGS_RELEASE:STRING"])

        self.assertEqual("", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

    @parameterized.expand([("True",), ("False", ), ])
    @unittest.skipIf(platform.system() == "Windows", "fPIC is not used for Windows")
    def test_fPIC(self, fpic):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure(options_dict={"app:fPIC": fpic})

        fpic_str = "ON" if fpic == "True" else "OFF"
        if fpic:
            self.assertIn("-- Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)",
                          configure_out)
        self.assertIn(">> CMAKE_POSITION_INDEPENDENT_CODE: {}".format(fpic_str), configure_out)

        self.assertNotIn("CONAN_CMAKE_POSITION_INDEPENDENT_CODE", cmake_cache_keys)
        self.assertNotIn("CMAKE_POSITION_INDEPENDENT_CODE", cmake_cache_keys)

    @unittest.skipIf(platform.system() != "Darwin", "rpath is only handled for Darwin")
    def test_rpath(self):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_INSTALL_NAME_DIR: ", configure_out)
        self.assertIn(">> CMAKE_SKIP_RPATH: 1", configure_out)
        self.assertEqual("1", cmake_cache["CMAKE_SKIP_RPATH:BOOL"])
