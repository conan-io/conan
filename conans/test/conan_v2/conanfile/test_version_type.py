import textwrap
import unittest

from jinja2 import Template

from conans.test.utils.tools import TestClient


from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class VersionTypeTestCase(ConanV2ModeTestCase):

    conanfile_tpl = Template(textwrap.dedent("""
        import six
        from conans import ConanFile
        from conans.errors import ConanException
        from conans.model.version import Version

        class Recipe(ConanFile):
            name = "name"
            {% if not use_set_version and version %}version = {{ version }}{% endif %}

            {% if use_set_version %}
            def set_version(self):
                self.version = {{ version }}
            {% endif %}

            def _checks(self, function_name):
                version_is_str = isinstance(self.version, six.string_types)
                if version_is_str:
                    self.output.info("> {}: version ok".format(function_name))
                else:
                    v_type = type(self.version)
                    raise ConanException("> {}: version is type '{}'".format(function_name, v_type))

                if isinstance(self.version, Version):
                    raise ConanException("> {}: version is type 'Version'".format(function_name))

            # Functions ordered according to documentation

            def source(self):
                self._checks("source")

            def build(self):
                self._checks("build")

            def package(self):
                self._checks("package")

            def package_info(self):
                self._checks("package_info")

            def configure(self):
                self._checks("configure")

            def config_options(self):
                self._checks("config_options")

            def requirements(self):
                self._checks("requirements")

            def build_requirements(self):
                self._checks("build_requirements")

            def system_requirements(self):
                self._checks("system_requirements")

            def imports(self):
                self._checks("imports")

            def package_id(self):
                self._checks("package_id")

            def build_id(self):
                self._checks("build_id")

            def deploy(self):
                self._checks("deploy")

            def init(self):
                #self._checks("init")
                pass
    """))

    def _run_testing(self, conanfile, ref_create=None, ref_install=None):
        t = self.get_client()
        t.save({"conanfile.py": conanfile})
        ref_create = ref_create or ""
        t.run("create . {}".format(ref_create))

        for func in ("source", "build", "package", "package_info", "configure", "config_options",
                     "requirements", "build_requirements", "system_requirements", "imports",
                     "package_id", "build_id", ):  # TODO: `init()` not here
            self.assertIn("> {}: version ok".format(func), t.out)

        ref_install = ref_install or ref_create
        t.run("install {} -g deploy".format(ref_install))
        self.assertIn("> deploy: version ok", t.out)

    def test_cli(self):
        conanfile = self.conanfile_tpl.render()
        self._run_testing(conanfile, ref_create="name/42@")

    def test_recipe_attribute(self):
        conanfile = self.conanfile_tpl.render(version='"42"')
        self._run_testing(conanfile, ref_create="name/42@")

        conanfile = self.conanfile_tpl.render(version='42')
        self._run_testing(conanfile, ref_create=None, ref_install="name/42@")

        conanfile = self.conanfile_tpl.render(version='42.23')
        self._run_testing(conanfile, ref_create=None, ref_install="name/42.23@")

    def test_set_functions(self):
        conanfile = self.conanfile_tpl.render(version='"42"', use_set_version=True)
        self._run_testing(conanfile, ref_create="name/42@")

        conanfile = self.conanfile_tpl.render(version='42', use_set_version=True)
        self._run_testing(conanfile, ref_create=None, ref_install="name/42@")

        conanfile = self.conanfile_tpl.render(version='42.23', use_set_version=True)
        self._run_testing(conanfile, ref_create=None, ref_install="name/42.23@")
