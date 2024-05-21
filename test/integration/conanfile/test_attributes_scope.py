import textwrap

from conan.test.utils.tools import TestClient


class TestAttributesScope:

    def test_cppinfo_not_in_package_id(self):
        # self.cpp_info is not available in 'package_id'
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):

                def package_id(self):
                    self.cpp_info.libs = ["A"]
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version', assert_error=True)
        assert "'self.cpp_info' access in 'package_id()' method is forbidden" in t.out

    def test_settings_not_in_package_id(self):
        # self.cpp_info is not available in 'package_id'
        t = TestClient()
        conanfile = textwrap.dedent("""
               from conan import ConanFile

               class Recipe(ConanFile):

                   def package_id(self):
                       self.settings
           """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version', assert_error=True)
        assert "'self.settings' access in 'package_id()' method is forbidden" in t.out

    def test_options_not_in_package_id(self):
        # self.cpp_info is not available in 'package_id'
        t = TestClient()
        conanfile = textwrap.dedent("""
               from conan import ConanFile

               class Recipe(ConanFile):

                   def package_id(self):
                       self.options
           """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version', assert_error=True)
        assert "'self.options' access in 'package_id()' method is forbidden" in t.out

    def test_info_not_in_package_info(self):
        t = TestClient()
        conanfile = textwrap.dedent("""
               from conan import ConanFile

               class Recipe(ConanFile):

                   def package_info(self):
                       self.info
           """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version', assert_error=True)
        assert "'self.info' access in 'package_info()' method is forbidden" in t.out

    def test_info_not_in_package(self):
        # self.info is not available in 'package'
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):

                def package(self):
                    self.info.clear()
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version -s os=Linux', assert_error=True)
        assert "'self.info' access in 'package()' method is forbidden" in t.out

    def test_no_settings(self):
        # self.setting is not available in 'source'
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                settings = "os",

                def source(self):
                    self.settings.os
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version -s os=Linux', assert_error=True)
        assert "'self.settings' access in 'source()' method is forbidden" in t.out

    def test_no_options(self):
        # self.setting is not available in 'source'
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                options = {'shared': [True, False]}

                def source(self):
                    self.options.shared
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version -o shared=False', assert_error=True)
        assert "'self.options' access in 'source()' method is forbidden" in t.out
