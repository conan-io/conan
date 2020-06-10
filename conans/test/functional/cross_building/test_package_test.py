import unittest
from conans.test.utils.tools import TestClient
import textwrap
from conans.client.tools import save
from conans.test.utils.tools import TestClient, GenConanfile
from jinja2 import Template


class TestPackageTestCase(unittest.TestCase):
    conanfile_tpl = Template(textwrap.dedent("""
        from conans import ConanFile, tools

        class Recipe(ConanFile):
            settings = "os"
            {{ build_requires|default("") }}

            {% raw %}
            def build(self):
                self.output.info(">> settings.os: {}".format(self.settings.os))
                self.output.info(">> settings_build.os: {}".format(self.settings_build.os))
                self.output.info(">> tools.get_env('INFO'): {}".format(tools.get_env("INFO")))

            def package_info(self):
                setattr(self.env_info, "INFO", "{}-{}".format(self.name, self.settings.os))

            def test(self):
                pass
            {% endraw %}

    """))

    conanfile_br = conanfile_tpl.render()
    conanfile = conanfile_tpl.render(build_requires='build_requires = "br1/version"')
    conanfile_test = conanfile_tpl.render(build_requires='build_requires = "br2/version"')

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    def setUp(self):
        self.t = TestClient()
        save(self.t.cache.settings_path, self.settings_yml)
        self.t.save({'br.py': self.conanfile_br,
                     'conanfile.py': self.conanfile,
                     'test_package/conanfile.py': self.conanfile_test,
                     'profile_host': '[settings]\nos=Host',
                     'profile_build': '[settings]\nos=Build',})
        self.t.run("export br.py br1/version@")
        self.t.run("export br.py br2/version@")

    def test_command_create(self):
        self.t.run("create . name/version@ --build=missing"
                   " --profile:host=profile_host --profile:build=profile_build")

        # Build requires are built in the 'build' context:
        self.assertIn("br1/version: >> settings.os: Build", self.t.out)
        self.assertIn("br1/version: >> settings_build.os: Build", self.t.out)
        self.assertIn("br1/version: >> tools.get_env('INFO'): None", self.t.out)

        self.assertIn("br2/version: >> settings.os: Build", self.t.out)
        self.assertIn("br2/version: >> settings_build.os: Build", self.t.out)
        self.assertIn("br2/version: >> tools.get_env('INFO'): None", self.t.out)

        # Package 'name' is built for the 'host' context (br1 as build_requirement)
        self.assertIn("name/version: >> settings.os: Host", self.t.out)
        self.assertIn("name/version: >> settings_build.os: Build", self.t.out)
        self.assertIn("name/version: >> tools.get_env('INFO'): br1-Build", self.t.out)

        # Test_package is executed with the same profiles as the package itself
        self.assertIn("name/version (test package): >> settings.os: Host", self.t.out)
        self.assertIn("name/version (test package): >> settings_build.os: Build", self.t.out)
        self.assertIn("name/version (test package): >> tools.get_env('INFO'): br2-Build", self.t.out)

    def test_command_test(self):
        self.t.run("export . name/version@")
        self.t.run("test test_package/conanfile.py name/version@ --build=missing"
                   " --profile:host=profile_host --profile:build=profile_build")

        # Build requires are built in the 'build' context:
        self.assertIn("br1/version: >> settings.os: Build", self.t.out)
        self.assertIn("br1/version: >> settings_build.os: Build", self.t.out)
        self.assertIn("br1/version: >> tools.get_env('INFO'): None", self.t.out)

        self.assertIn("br2/version: >> settings.os: Build", self.t.out)
        self.assertIn("br2/version: >> settings_build.os: Build", self.t.out)
        self.assertIn("br2/version: >> tools.get_env('INFO'): None", self.t.out)

        # Package 'name' is built for the 'host' context (br1 as build_requirement)
        self.assertIn("name/version: >> settings.os: Host", self.t.out)
        self.assertIn("name/version: >> settings_build.os: Build", self.t.out)
        self.assertIn("name/version: >> tools.get_env('INFO'): br1-Build", self.t.out)

        # Test_package is executed with the same profiles as the package itself
        self.assertIn("name/version (test package): >> settings.os: Host", self.t.out)
        self.assertIn("name/version (test package): >> settings_build.os: Build", self.t.out)
        self.assertIn("name/version (test package): >> tools.get_env('INFO'): br2-Build", self.t.out)
