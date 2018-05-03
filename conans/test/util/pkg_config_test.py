#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import platform
import os
from nose.plugins.attrib import attr
from conans.tools import PkgConfig, environment_append
from conans.test.utils.test_files import temp_folder
from conans.errors import ConanException

libastral_pc = """
PC FILE EXAMPLE:

prefix=/usr/local
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: libastral
Description: Interface library for Astral data flows
Version: 6.6.6
Libs: -L${libdir}/libastral -lastral -Wl,--whole-archive
Cflags: -I${includedir}/libastral -D_USE_LIBASTRAL
"""


@attr("unix")
class PkgConfigTest(unittest.TestCase):
    def test_negative(self):
        if platform.system() == "Windows":
            return
        pc = PkgConfig('libsomething_that_does_not_exist_in_the_world')
        with self.assertRaises(ConanException):
            pc.libs()

    def test_pc(self):
        if platform.system() == "Windows":
            return
        tmp_dir = temp_folder()
        filename = os.path.join(tmp_dir, 'libastral.pc')
        with open(filename, 'w') as f:
            f.write(libastral_pc)
        with environment_append({'PKG_CONFIG_PATH': tmp_dir}):
            pkg_config = PkgConfig("libastral")

            self.assertEquals(frozenset(pkg_config.cflags), frozenset(['-D_USE_LIBASTRAL', '-I/usr/local/include/libastral']))
            self.assertEquals(frozenset(pkg_config.cflags_only_I), frozenset(['-I/usr/local/include/libastral']))
            self.assertEquals(frozenset(pkg_config.cflags_only_other), frozenset(['-D_USE_LIBASTRAL']))

            self.assertEquals(frozenset(pkg_config.libs), frozenset(['-L/usr/local/lib/libastral', '-lastral', '-Wl,--whole-archive']))
            self.assertEquals(frozenset(pkg_config.libs_only_L), frozenset(['-L/usr/local/lib/libastral']))
            self.assertEquals(frozenset(pkg_config.libs_only_l), frozenset(['-lastral',]))
            self.assertEquals(frozenset(pkg_config.libs_only_other), frozenset(['-Wl,--whole-archive']))

            self.assertEquals(pkg_config.variables['prefix'], '/usr/local')
        os.unlink(filename)

    def test_define_prefix(self):
        if platform.system() == "Windows":
            return
        tmp_dir = temp_folder()
        filename = os.path.join(tmp_dir, 'libastral.pc')
        with open(filename, 'w') as f:
            f.write(libastral_pc)
        with environment_append({'PKG_CONFIG_PATH': tmp_dir}):
            pkg_config = PkgConfig("libastral", variables={'prefix': '/home/conan'})

            self.assertEquals(frozenset(pkg_config.cflags),
                              frozenset(['-D_USE_LIBASTRAL', '-I/home/conan/include/libastral']))
            self.assertEquals(frozenset(pkg_config.cflags_only_I), frozenset(['-I/home/conan/include/libastral']))
            self.assertEquals(frozenset(pkg_config.cflags_only_other), frozenset(['-D_USE_LIBASTRAL']))

            self.assertEquals(frozenset(pkg_config.libs),
                              frozenset(['-L/home/conan/lib/libastral', '-lastral', '-Wl,--whole-archive']))
            self.assertEquals(frozenset(pkg_config.libs_only_L), frozenset(['-L/home/conan/lib/libastral']))
            self.assertEquals(frozenset(pkg_config.libs_only_l), frozenset(['-lastral', ]))
            self.assertEquals(frozenset(pkg_config.libs_only_other), frozenset(['-Wl,--whole-archive']))

            self.assertEquals(pkg_config.variables['prefix'], '/home/conan')
        os.unlink(filename)

    def rpaths_libs_test(self):
        if platform.system() == "Windows":
            return
        pc_content = """prefix=/my_prefix/path
libdir=/my_absoulte_path/fake/mylib/lib
libdir3=${prefix}/lib2
includedir=/my_absoulte_path/fake/mylib/include

Name: MyLib
Description: Conan package: MyLib
Version: 0.1
Libs: -L${libdir} -L${libdir3} -Wl,-rpath="${libdir}" -Wl,-rpath="${libdir3}"
Cflags: -I${includedir}"""
        tmp_dir = temp_folder()
        filename = os.path.join(tmp_dir, 'MyLib.pc')
        with open(filename, 'w') as f:
            f.write(pc_content)
        with environment_append({'PKG_CONFIG_PATH': tmp_dir}):
            expected = ("-L/my_absoulte_path/fake/mylib/lib "
                        "-L/my_prefix/path/lib2 "
                        "-Wl,-rpath=/my_absoulte_path/fake/mylib/lib "
                        "-Wl,-rpath=/my_prefix/path/lib2")
            pkg_config = PkgConfig("MyLib")
            self.assertIn(expected, " ".join(lib for lib in pkg_config.libs))
