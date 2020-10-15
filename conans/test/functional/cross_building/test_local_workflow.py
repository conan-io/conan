import unittest
import textwrap


class LocalWorkflowTestCase(unittest.TestCase):
    br_conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            def package_info(self):
                self.cpp_info
    """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            build_requires = 'br/version'

            def build(self):
                self.output.info(">> tools.get_env('INFO'): {}".format(tools.get_env("INFO")))
    """)
