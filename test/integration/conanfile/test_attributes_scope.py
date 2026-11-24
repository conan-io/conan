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

    def test_python_requires_extend(self):
        # The recipes that extend the same python_requires class each keep their own class (name,
        # methods) while their attributes are forbidden, also in the inherited methods
        t = TestClient()
        pyreq = textwrap.dedent("""
            from conan import ConanFile

            class MyBase:
                def validate(self):
                    self.output.info(f"base validate of {self.name}, os={self.settings.os}")

                def package_id(self):
                    self.output.info(f"base package_id of {self.name}")
                    if self.forbidden_in_package_id:
                        self.settings

                def package_info(self):
                    self.output.info(f"base package_info of {self.name}")

            class PyReq(ConanFile):
                name = "pyreq"
                version = "0.1"
                package_type = "python-require"
            """)
        pkg = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "{name}"
                version = "0.1"
                settings = "os"
                python_requires = "pyreq/0.1"
                python_requires_extend = "pyreq.MyBase"
                forbidden_in_package_id = {forbidden}

                def package_info(self):
                    super().package_info()
                    self.output.info(f"own package_info of {{self.name}}")
                    {extra}
            """)
        t.save({"pyreq/conanfile.py": pyreq,
                "pkga/conanfile.py": pkg.format(name="pkga", forbidden=False, extra=""),
                "pkgb/conanfile.py": pkg.format(name="pkgb", forbidden=False, extra=""),
                "pkgc/conanfile.py": pkg.format(name="pkgc", forbidden=True, extra=""),
                "pkgd/conanfile.py": pkg.format(name="pkgd", forbidden=False,
                                                extra="self.info")})
        t.run("create pyreq")
        t.run("create pkgc -s os=Linux", assert_error=True)
        assert "base package_id of pkgc" in t.out
        assert "'self.settings' access in 'package_id()' method is forbidden" in t.out
        t.run("create pkgd -s os=Linux", assert_error=True)
        assert "own package_info of pkgd" in t.out
        assert "'self.info' access in 'package_info()' method is forbidden" in t.out

        t.run("create pkga -s os=Linux")
        t.run("create pkgb -s os=Linux")
        t.run("install --requires=pkga/0.1 --requires=pkgb/0.1 -s os=Linux")
        for name in ("pkga", "pkgb"):
            assert f"{name}/0.1: base validate of {name}, os=Linux" in t.out
            assert f"{name}/0.1: base package_id of {name}" in t.out
            assert f"{name}/0.1: base package_info of {name}" in t.out
            assert f"{name}/0.1: own package_info of {name}" in t.out
