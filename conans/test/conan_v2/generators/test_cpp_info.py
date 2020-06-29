import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class CppInfoTestCase(ConanV2ModeTestCase):

    def test_cpp_info_name(self):
        t = self.get_client()
        lib = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "lib"

                def package_info(self):
                    self.cpp_info.name = "lib_name"
        """)
        app = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "app"
                requires = "lib/version"

                def build(self):
                    lib_cpp_info = self.deps_cpp_info["lib"]
                    self.output.info("get_name: {}".format(lib_cpp_info.get_name('cmake')))
                    self.output.info("name: {}".format(lib_cpp_info.name))
        """)

        t.save({'lib.py': lib,
                'app.py': app})
        t.run('export lib.py lib/version@')
        t.run('create app.py app/version@ --build=missing', assert_error=True)

        self.assertIn("app/version: get_name: lib_name", t.out)
        self.assertIn("ConanV2Exception: Conan v2 incompatible: Use 'get_name(generator)' instead",
                      t.out)
