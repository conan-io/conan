import json
import os
import textwrap
import unittest

from conans.client.tools import save, load
from conans.test.utils.tools import TestClient


class DefaultCppTestCase(unittest.TestCase):
    compiler = "gcc"
    compiler_version = "7"

    default_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86
        compiler=gcc
        compiler.version=7
        compiler.libcxx=libstdc++11
        """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Library(ConanFile):
            settings = "os", "compiler"

            def configure(self):
                compiler_cppstd = self.settings.get_safe("compiler.cppstd")
                self.output.info("compiler.cppstd: {}!!".format(compiler_cppstd))
        """)

    id_default = "827ab7c8bacdca7433f4463313dfe30219f13843"

    def setUp(self):
        self.t = TestClient()
        save(self.t.cache.default_profile_path, self.default_profile)
        # Compute ID without the setting 'cppstd'
        target_id, output = self._get_id({})
        self.assertEqual(target_id, self.id_default)
        self.assertIn("compiler.cppstd: None!!", output)

    def _get_id(self, settings_values):
        # Create the conanfile with corresponding settings
        self.t.save({"conanfile.py": self.conanfile}, clean_first=True)

        # Create the string with the command line settings
        settings_values_str = ["-s {k}={v}".format(k=k, v=v) for k, v in settings_values.items()]
        settings_values_str = " ".join(settings_values_str)

        # Call `conan info`
        json_file = os.path.join(self.t.current_folder, "tmp.json")
        self.t.run('info . {} --json="{}"'.format(settings_values_str, json_file))
        info_output = self.t.out
        data = json.loads(load(json_file))
        self.assertEqual(len(data), 1)

        # Return ID, output
        return data[0]["id"], info_output

    def test_value_none(self):
        # Explicit value 'None' passed to setting 'cppstd'
        id_with, output = self._get_id(settings_values={"compiler.cppstd": "None"})
        self.assertIn("compiler.cppstd: None!!", output)
        self.assertEqual(self.id_default, id_with)

    def test_value_other(self):
        # Explicit value (not the default) passed to setting 'cppstd'
        id_with, output = self._get_id(settings_values={"compiler.cppstd": "14"})
        self.assertIn("compiler.cppstd: 14!!", output)
        self.assertNotEqual(self.id_default, id_with)
