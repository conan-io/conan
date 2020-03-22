import unittest
from parameterized import parameterized

from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.errors import ConanInvalidConfiguration, ConanException

from conans.tools import check_compiler


class CheckCompilerTests(unittest.TestCase):

    def test_user_inputs(self):
        """ Inputs with incorrect types should throw ConanException
        """
        conanfile = MockConanfile(MockSettings({}))

        with self.assertRaises(ConanException) as raises:
            check_compiler(conanfile, required=[])
        self.assertEqual("required parameter must be a dict", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            check_compiler(conanfile, required={}, strict="Yes")
        self.assertEqual("strict parameter must be a bool", str(raises.exception))

    def _create_conanfile(self, compiler, version, os, cppstd, libcxx=None):
        settings = MockSettings({"arch": "x86_64",
                                 "build_type": "Debug",
                                 "os": os,
                                 "compiler": compiler,
                                 "compiler.version": version,
                                 "compiler.cppstd": cppstd})
        if libcxx:
            settings.values["compiler.libcxx"] = libcxx
        conanfile = MockConanfile(settings)
        return conanfile

    @parameterized.expand(["5", "6", "7", "8"])
    def test_check_compiler_from_settings(self, version):
        """ check_compiler must accept compiler.version less/equal than
            compiler.version in settings
        """
        conanfile = self._create_conanfile("gcc", version, "Linux", None, "libstdc++")
        check_compiler(conanfile, required={"gcc": "5"})

    @parameterized.expand(["6", "7", "8"])
    def test_check_compiler_from_outdated_settings(self, version):
        """ check_compiler must raise when compiler.version in settings is less than required
        """
        conanfile = self._create_conanfile("gcc", "5", "Linux", None, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_compiler(conanfile, required={"gcc": version})
        self.assertEqual("At least gcc {} is required".format(version), str(raises.exception))

    def test_compiler_not_specified(self):
        """ check_compiler must raise if compiler information is missing
        """
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            conanfile = self._create_conanfile(None, "9", "Linux", None, "libstdc++")
            check_compiler(conanfile, required={"gnu": "5"})
        self.assertIn("compiler is not specified", str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            conanfile = self._create_conanfile("gnu", None, "Linux", None, "libstdc++")
            check_compiler(conanfile, required={"gnu": "5"})
        self.assertIn("compiler.version is not specified", str(raises.exception))

    def test_check_compiler_missing(self):
        """ check_compiler must warn when compiler is not specified in requirements
        """
        conanfile = self._create_conanfile("gcc", "5", "Linux", None, "libstdc++")
        check_compiler(conanfile, required={"something_else": "5"})
        self.assertIn("WARN: Compiler support information is missing", conanfile.output)

    def test_check_compiler_strict(self):
        """ check_compiler must raise when compiler is not specified in requirements
            only if the strict mode is enabled
        """
        conanfile = self._create_conanfile("gcc", "5", "Linux", None, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_compiler(conanfile, required={}, strict=True)
        self.assertEqual("Compiler support information is missing", str(raises.exception))
