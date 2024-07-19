import textwrap
import unittest

from jinja2 import Template

from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestPackageTestCase(unittest.TestCase):
    conanfile_tpl = Template(textwrap.dedent("""
        from conan import ConanFile
        import os
        from conan.tools.env import VirtualBuildEnv

        class Recipe(ConanFile):
            settings = "os"
            {{ build_requires|default("") }}

            {% if test %}
            def requirements(self):
                self.requires(self.tested_reference_str)
            {% endif %}

            {% raw %}
            def build(self):
                self.output.info(">> settings.os: {}".format(self.settings.os))
                self.output.info(">> settings_build.os: {}".format(self.settings_build.os))
                build_env = VirtualBuildEnv(self).vars()
                with build_env.apply():
                    self.output.info(">> tools.get_env('INFO'): {}".format(os.getenv("INFO")))

            def package_info(self):
                self.buildenv_info.define("INFO", "{}-{}".format(self.name, self.settings.os))

            def test(self):
                pass
            {% endraw %}

    """))

    conanfile_br = conanfile_tpl.render()
    conanfile = conanfile_tpl.render(build_requires='build_requires = "br1/version"')
    conanfile_test = conanfile_tpl.render(build_requires='build_requires = "br2/version"',
                                          test=True)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    def test_command(self):
        t = TestClient()
        save(t.cache.settings_path, self.settings_yml)
        t.save({'br.py': self.conanfile_br,
                'conanfile.py': self.conanfile,
                'test_package/conanfile.py': self.conanfile_test,
                'profile_host': '[settings]\nos=Host',
                'profile_build': '[settings]\nos=Build', })
        t.run("export br.py --name=br1 --version=version")
        # It is necessary to build first the test_package build_requires br2
        t.run("create br.py --name=br2 --version=version -tf=\"\" --build-require "
              "--profile:host=profile_host --profile:build=profile_build")

        t.run("create conanfile.py --name=name --version=version --build=missing"
              " --profile:host=profile_host --profile:build=profile_build")

        # Build requires are built in the 'build' context:
        self.assertIn("br1/version: >> settings.os: Build", t.out)
        self.assertIn("br1/version: >> settings_build.os: Build", t.out)

        # Package 'name' is built for the 'host' context (br1 as build_requirement)
        self.assertIn("name/version: >> settings.os: Host", t.out)
        self.assertIn("name/version: >> settings_build.os: Build", t.out)

        # Test_package is executed with the same profiles as the package itself
        self.assertIn("name/version (test package): >> settings.os: Host", t.out)
        self.assertIn("name/version (test package): >> settings_build.os: Build", t.out)

        t.run("test test_package/conanfile.py name/version@ "
              "--profile:host=profile_host --profile:build=profile_build")

        assert "name/version (test package): >> settings.os: Host" in t.out
        assert "name/version (test package): >> settings_build.os: Build" in t.out
        assert "name/version (test package): >> tools.get_env('INFO'): br2-Build" in t.out
