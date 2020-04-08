import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class PythonRequiresTestCase(ConanV2ModeTestCase):

    def test_deprecate_old_syntax(self):
        # It raises if used, not if it is just imported
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, python_requires

            base = python_requires("pyreq/version@user/channel")
            class Recipe(ConanFile):
                pass
        """)
        t.save({'conanfile.py': conanfile})
        t.run('export . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: Old syntax for python_requires is deprecated", t.out)
