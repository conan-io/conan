import textwrap
import unittest

from conan.test.utils.tools import TestClient


class ConanfileRepeatedGeneratorsTestCase(unittest.TestCase):

    def test_conanfile_txt(self):
        conanfile = textwrap.dedent("""
            [generators]
            CMakeDeps
            CMakeDeps
        """)

        t = TestClient()
        t.save({'conanfile.txt': conanfile})
        t.run("install conanfile.txt")
        self.assertEqual(str(t.out).count("Generator 'CMakeDeps' calling 'generate()'"), 1)

    def test_conanfile_py(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                settings = "build_type"
                generators = "CMakeDeps", "CMakeDeps"
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("install conanfile.py")
        self.assertEqual(str(t.out).count("Generator 'CMakeDeps' calling 'generate()'"), 1)

    def test_python_requires_inheritance(self):
        pyreq = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                pass

            class BaseConan(object):
                generators = "CMakeDeps",
        """)
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                settings = "build_type"
                python_requires = "base/1.0"
                python_requires_extend = "base.BaseConan"
                settings = "build_type"
                generators = "CMakeDeps",

                def init(self):
                    base = self.python_requires["base"].module.BaseConan
                    self.generators = base.generators + self.generators
        """)

        t = TestClient()
        t.save({'pyreq.py': pyreq, 'conanfile.py': conanfile})
        t.run("export pyreq.py --name=base --version=1.0")
        t.run("install conanfile.py")
        self.assertEqual(str(t.out).count("Generator 'CMakeDeps' calling 'generate()'"), 1)

    def test_duplicated_generator_in_member_and_attribue(self):
        """
        Ensure we raise an error when a generator is present both in the generators attribute
        and instanced in the generate() method by the user, which we didn't use to do before 2.0
        """
        conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain

        class Recipe(ConanFile):
            generators = "CMakeToolchain"

            def generate(self):
                tc = CMakeToolchain(self)
                tc.generate()
        """)

        t = TestClient()
        t.save({'conanfile.py': conanfile})
        # This used to not throw any errors
        t.run("install .", assert_error=True)
        assert "was instantiated in the generate() method too" in t.out
