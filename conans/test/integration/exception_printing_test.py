import unittest

from conans import tools
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


class ExceptionPrintingTest(unittest.TestCase):
    conanfile = """
import os
from conans import ConanFile

class DRLException(Exception):
    pass

class ExceptionsTest(ConanFile):
    name = "ExceptionsTest"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def source(self):
        {source_contents}

    def build(self):
        {build_contents}

    def package(self):
        {package_contents}

    def package_info(self):
        {package_info_contents}

    def configure(self):
        {configure_contents}

    def build_id(self):
        {build_id_contents}

    def package_id(self):
        {package_id_contents}

    def requirements(self):
        {requirements_contents}

    def config_options(self):
        {config_options_contents}

    def _aux_method(self):
        raise DRLException('Oh! an error!')
"""

    def setUp(self):
        self.client = TestClient()

    def _call_install(self, conanfile):
        self.client.save({CONANFILE: conanfile}, clean_first=True)
        self.client.run("export . lasote/stable")
        with self.assertRaises(Exception):
            with tools.environment_append({"CONAN_USERNAME": "lasote", "CONAN_CHANNEL": "stable"}):
                self.client.run("install ExceptionsTest/0.1@lasote/stable --build")

    def _test_fail_line(self, conanfile, numline, method_name):
        self._call_install(conanfile)
        self.assertIn("ExceptionsTest/0.1@lasote/stable: Error in %s() method, line %s" % (method_name, numline), self.client.user_io.out)
        self.assertIn("DRLException: Oh! an error!", self.client.user_io.out)

    def _get_conanfile_for(self, method_name):
        throw = "raise DRLException('Oh! an error!')"
        cf = self.conanfile.format(source_contents=throw if method_name == "source" else "pass",
                                   build_contents=throw if method_name == "build" else "pass",
                                   package_contents=throw if method_name == "package" else "pass",
                                   package_info_contents=throw if method_name == "package_info" else "pass",
                                   configure_contents=throw if method_name == "configure" else "pass",
                                   build_id_contents=throw if method_name == "build_id" else "pass",
                                   package_id_contents=throw if method_name == "package_id" else "pass",
                                   requirements_contents=throw if method_name == "requirements" else "pass",
                                   config_options_contents=throw if method_name == "config_options" else "pass")
        return cf

    def _test_fail_line_aux(self, conanfile, main_line, numline, method_name):
        self._call_install(conanfile)
        self.assertIn("ExceptionsTest/0.1@lasote/stable: Error in %s() method, line %s" % (method_name, main_line),
                      self.client.user_io.out)
        self.assertIn("\nwhile calling '_aux_method', line %s" % numline,
                      self.client.user_io.out)

        self.assertIn("DRLException: Oh! an error!", self.client.user_io.out)

    def _get_conanfile_for_error_in_other_method(self, method_name):
        throw = "self._aux_method()"
        cf = self.conanfile.format(source_contents=throw if method_name == "source" else "pass",
                                   build_contents=throw if method_name == "build" else "pass",
                                   package_contents=throw if method_name == "package" else "pass",
                                   package_info_contents=throw if method_name == "package_info" else "pass",
                                   configure_contents=throw if method_name == "configure" else "pass",
                                   build_id_contents=throw if method_name == "build_id" else "pass",
                                   package_id_contents=throw if method_name == "package_id" else "pass",
                                   requirements_contents=throw if method_name == "requirements" else "pass",
                                   config_options_contents=throw if method_name == "config_options" else "pass")
        return cf

    def test_all_methods(self):

        for method, line in [("source", 14), ("build", 17),
                             ("package", 20), ("package_info", 23),
                             ("configure", 26), ("build_id", 29),
                             ("package_id", 32), ("requirements", 35),
                             ("config_options", 38)]:
            self._test_fail_line(self._get_conanfile_for(method), line, method)

    def test_aux_method(self):
        for method, main_line, line in [("source", 14, 41), ("build", 17, 41),
                                        ("package", 20, 41), ("package_info", 23, 41),
                                        ("configure", 26, 41), ("build_id", 29, 41),
                                        ("package_id", 32, 41), ("requirements", 35, 41),
                                        ("config_options", 38, 41)]:
            self._test_fail_line_aux(self._get_conanfile_for_error_in_other_method(method),
                                     main_line, line, method)

    def test_complete_traceback(self):
        with tools.environment_append({"CONAN_VERBOSE_TRACEBACK": "1"}):
            self._call_install(self._get_conanfile_for_error_in_other_method("source"))
            self.assertIn("ERROR: Traceback (most recent call last):", self.client.user_io.out)
            self.assertIn('self._aux_method()', self.client.user_io.out)
            self.assertIn("raise DRLException('Oh! an error!')", self.client.user_io.out)


if __name__ == '__main__':
    unittest.main()
