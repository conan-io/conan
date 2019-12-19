import unittest

from conans import Layout
from conans.test.utils.conanfile import MockConanfile, MockSettings


class DevLayoutModelTest(unittest.TestCase):

    def base_class_defaults_test(self):
        settings = MockSettings({})
        cf = MockConanfile(settings)
        ly = Layout(cf)
        self.assertEqual(ly.build, "build")
        self.assertEqual(ly.src, "")
        self.assertEqual(ly.build_libdir, "")
        self.assertEqual(ly.build_bindir, "")
        self.assertEqual(ly.build_includedirs, [ly.build, ly.src])
        self.assertIsNone(ly.build_installdir)
        self.assertEqual(ly.pkg_libdir, "lib")
        self.assertEqual(ly.pkg_bindir, "bin")
        self.assertEqual(ly.pkg_includedir, "include")
        self.assertEqual(ly.pkg_builddir, "build")

    def clion_defaults_test(self):
        # Depending on build type
        # TODO
        pass

    def cmake_defaults_test(self):
        # Depending on build type
        # TODO
        pass

    def folders_test(self):
        # TODO: default install dir, other composed...
        pass