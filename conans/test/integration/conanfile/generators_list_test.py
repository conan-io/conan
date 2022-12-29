import textwrap
import unittest

from conans.test.utils.tools import TestClient


class ConanfileRepeatedGeneratorsTestCase(unittest.TestCase):

    def test_conanfile_txt(self):
        conanfile = textwrap.dedent("""
            [generators]
            cmake
            CMakeDeps
            cmake
        """)

        t = TestClient()
        t.save({'conanfile.txt': conanfile})
        t.run("install conanfile.txt")
        self.assertEqual(str(t.out).count("Generator cmake created"), 1)

    def test_conanfile_py(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "build_type"
                generators = "cmake", "CMakeDeps", "cmake"
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("install conanfile.py")
        self.assertEqual(str(t.out).count("Generator cmake created"), 1)

    def test_python_requires_inheritance(self):
        pyreq = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                pass

            class BaseConan(object):
                generators = "cmake", "CMakeDeps"
        """)
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "build_type"
                python_requires = "base/1.0"
                python_requires_extend = "base.BaseConan"

                generators = "cmake", "CMakeDeps"

                def init(self):
                    base = self.python_requires["base"].module.BaseConan
                    self.generators = base.generators + self.generators
        """)

        t = TestClient()
        t.save({'pyreq.py': pyreq, 'conanfile.py': conanfile})
        t.run("export pyreq.py base/1.0@")
        t.run("install conanfile.py")
        self.assertEqual(str(t.out).count("Generator cmake created"), 1)
