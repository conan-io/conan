import textwrap
import unittest

from jinja2 import Template
from parameterized import parameterized

from conans.client.tools import save
from conans.test.utils.tools import TestClient


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

    @parameterized.expand([("create conanfile.py name/version@",),
                           ("test test_package/conanfile.py name/version@",)])
    def test_command(self, command):
        t = TestClient()
        save(t.cache.settings_path, self.settings_yml)
        t.save({'br.py': self.conanfile_br,
                'conanfile.py': self.conanfile,
                'test_package/conanfile.py': self.conanfile_test,
                'profile_host': '[settings]\nos=Host',
                'profile_build': '[settings]\nos=Build', })
        t.run("export br.py br1/version@")
        t.run("export br.py br2/version@")
        t.run("export conanfile.py name/version@")

        # Execute the actual command we are testing
        t.run(command + " --build=missing --profile:host=profile_host --profile:build=profile_build")

        # Build requires are built in the 'build' context:
        self.assertIn("br1/version: >> settings.os: Build", t.out)
        self.assertIn("br1/version: >> settings_build.os: Build", t.out)
        self.assertIn("br1/version: >> tools.get_env('INFO'): None", t.out)

        self.assertIn("br2/version: >> settings.os: Build", t.out)
        self.assertIn("br2/version: >> settings_build.os: Build", t.out)
        self.assertIn("br2/version: >> tools.get_env('INFO'): None", t.out)

        # Package 'name' is built for the 'host' context (br1 as build_requirement)
        self.assertIn("name/version: >> settings.os: Host", t.out)
        self.assertIn("name/version: >> settings_build.os: Build", t.out)
        self.assertIn("name/version: >> tools.get_env('INFO'): br1-Build", t.out)

        # Test_package is executed with the same profiles as the package itself
        self.assertIn("name/version (test package): >> settings.os: Host", t.out)
        self.assertIn("name/version (test package): >> settings_build.os: Build", t.out)
        self.assertIn("name/version (test package): >> tools.get_env('INFO'): br2-Build", t.out)
