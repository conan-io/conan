import textwrap
import unittest

from urllib3.packages import six

from conans.paths import LAYOUT_PY
from conans.test.utils.tools import TestClient, GenConanfile


class LayoutLoadTest(unittest.TestCase):

    def test_method_layout_load(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
              from conans import ConanFile, CMake, CMakeLayout

              class Pkg(ConanFile):
                  settings = "os", "compiler", "arch", "build_type"

                  def layout(self):
                      self.lyt = CMakeLayout(self)
                      self.lyt.build = "mybuild"
                      self.lyt.src = "mysrc"

                  def assert_layout(self):
                      assert self.lyt.build == "mybuild"
                      assert self.lyt.src == "mysrc"

                  def build(self):
                      self.assert_layout()

                  def package(self):
                      self.assert_layout()

                  def package_info(self):
                      self.assert_layout()
                  """)
        client.save({"conanfile.py": conanfile})

        client.run("create . lib/1.0@")
        self.assertIn("Created package revision", client.out)

        # Virtual load
        client.run("install lib/1.0@")

    def test_text_layout_load(self):
        """Declare the layout using the layout text attribute"""
        client = TestClient()
        conanfile = textwrap.dedent("""
           import platform
           from conans import ConanFile, CMake

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               layout = "cmake"

               def assert_layout(self):
                   assert self.layout == "cmake"
                   assert self.lyt.build == "build" if platform.system == "Windows" \
                                else "cmake-build-{}".format(str(self.settings.build_type))
                   assert self.lyt.src == ""

               def build(self):
                   self.assert_layout()

               def package(self):
                   self.assert_layout()

               def package_info(self):
                   self.assert_layout()
               """)
        client.save({"conanfile.py": conanfile})

        client.run("create . lib/1.0@")
        self.assertIn("Created package revision", client.out)

        # Virtual load
        client.run("install lib/1.0@")

    @unittest.skipIf(six.PY2, "Needs PY3")
    def load_layout_py_local_methods_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile, CMake

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               layout = "cmake"

               def build(self):
                   assert self.lyt.build == "overwritten_build"
                   assert self.lyt.src == "overwritten_src"
                   self.output.warn("Here, building")
               """)
        override_layout = textwrap.dedent("""
        from conans import DefaultLayout

        def layout(self):
            self.lyt = DefaultLayout(self)
            self.lyt.build = "overwritten_build"
            self.lyt.src = "overwritten_src"
        """)
        client.save({"conanfile.py": conanfile, LAYOUT_PY: override_layout})
        client.run("install .")
        # If not specified in the layout, layout.build_installdir is defauted to layout.build
        client.run("build . -if=overwritten_build")
        self.assertIn("Here, building", client.out)

    def not_load_layout_create_test(self):
        """The LAYOUT_PY file is not used with a Conan create because the package is in the cache
           and this is only intended to work only for packages being edited (local methods +
           editables) Otherwise a package in the cache would have been generated with a "patchy"
           conanfile.
           """
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile, CMake

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               layout = "cmake"

               def build(self):
                   assert self.lyt.build != "overwritten_build"
                   self.output.warn("Here, building")
               """)
        override_layout = textwrap.dedent("""
        from conans import DefaultLayout

        def layout(self):
            self.lyt = DefaultLayout(self)
            self.lyt.build = "overwritten_build"
            self.lyt.src = "overwritten_src"
        """)
        client.save({"conanfile.py": conanfile, LAYOUT_PY: override_layout})
        client.run("create . lib/1.0@")
        self.assertIn("Here, building", client.out)

    @unittest.skipIf(six.PY2, "Needs PY3")
    def editable_load_layout_create_test(self):
        """If the package is in editable mode, the LAYOUT_PY is also used"""
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile, CMake

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               layout = "cmake"

               def build(self):
                   assert self.lyt.build == "overwritten_build"
                   assert self.lyt.src == "overwritten_src"
                   self.output.warn("Here, building")

               def package_info(self):
                    self.output.warn("Here, being reused: {}".format(self.lyt.build))
               """)
        override_layout = textwrap.dedent("""
        from conans import DefaultLayout

        def layout(self):
            self.lyt = DefaultLayout(self)
            self.lyt.build = "overwritten_build"
            self.lyt.src = "overwritten_src"
        """)
        client.save({"conanfile.py": conanfile, LAYOUT_PY: override_layout})
        client.run("install . ")
        client.run("build . -if=overwritten_build")
        client.run("editable add . lib/1.0@")
        client.run("install lib/1.0@")
        self.assertIn("Here, being reused: overwritten_build", client.out)

    def returning_non_layout_in_method_test(self):
        """If you assign the layout badly in the method..."""
        client = TestClient()
        conanfile = textwrap.dedent("""
                   import os
                   from conans import ConanFile, CMake

                   class Pkg(ConanFile):
                       def layout(self):
                           pass

                       def build(self):
                           self.lyt.build_folder

                       """)
        client.save({"conanfile.py": conanfile})
        client.run("create . lib/1.0@", assert_error=True)
        self.assertIn("The layout() method is not assigning a DefaultLayout object to self.lyt",
                      client.out)

    def invalid_layout_type_test(self):
        """If you forget to return the layout in the method..."""
        client = TestClient()
        conanfile = textwrap.dedent("""
                   import os
                   from conans import ConanFile, CMake

                   class Pkg(ConanFile):
                       layout = 34

                       def build(self):
                           self.lyt.build_folder

                       """)
        client.save({"conanfile.py": conanfile})
        client.run("create . lib/1.0@", assert_error=True)
        self.assertIn("Unexpected layout type declared in the conanfile: 'int'",
                      client.out)

    @unittest.skipIf(six.PY2, "Needs PY3")
    def invalid_layout_override_test(self):
        client = TestClient()
        conanfile = GenConanfile().with_text_layout("cmake")
        overwrite = """
def wrong_function():
    pass
"""
        client.save({"conanfile.py": conanfile, LAYOUT_PY: overwrite})
        client.run("install .", assert_error=True)
        self.assertIn("The file {} has no 'layout()' method".format(LAYOUT_PY), client.out)

        overwrite = """
def layout(self):
    pass # Not assigning
"""
        client.save({LAYOUT_PY: overwrite})
        client.run("install .", assert_error=True)
        self.assertIn("The layout() method is not assigning a DefaultLayout object to self.ly",
                      client.out)

    @unittest.skipUnless(six.PY2, "Needs PY2")
    def check_layout_override_py2_only_test(self):
        client = TestClient()
        conanfile = GenConanfile().with_text_layout("cmake")
        overwrite = """
def layout(self):
    pass
        """
        client.save({"conanfile.py": conanfile, LAYOUT_PY: overwrite})
        client.run("install .", assert_error=True)
        self.assertIn("The {} feature is Python3 only".format(LAYOUT_PY), client.out)
