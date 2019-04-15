# coding=utf-8

import json
import os
import textwrap
import unittest

from conans.client.build.cppstd_flags import cppstd_default
from conans.client.tools import environment_append, save, load
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class DefaultCppTestCase(unittest.TestCase):
    # Validate package ID computed taking into account different cppstd scenarios

    compiler = "gcc"
    compiler_version = "7"

    default_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86
        compiler={}
        compiler.version={}
        compiler.libcxx=libstdc++11
        """.format(compiler, compiler_version))

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Library(ConanFile):
            settings = "{settings}"

            def configure(self):
                cppstd = self.settings.get_safe("cppstd")
                self.output.info(">>>> settings: {{}}".format(self.settings.fields))
                self.output.info(">>>> cppstd: {{}}".format(cppstd))
        """)

    id_default = "d17189cfe7b11efbc5d701339a32d203745f8b81"

    def run(self, *args, **kwargs):
        # Create and use a different default profile
        default_profile_path = os.path.join(temp_folder(), "default.profile")
        save(default_profile_path, self.default_profile)
        with environment_append({"CONAN_DEFAULT_PROFILE_PATH": default_profile_path}):
            super(DefaultCppTestCase, self).run(*args, **kwargs)

    def setUp(self):
        self.t = TestClient()
        # Compute ID without the setting 'cppstd'
        self.target_id, output = self._get_id(with_cppstd=False)
        self.assertEqual(self.target_id, self.id_default)
        self.assertIn(">>>> settings: ['compiler', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)

    def _get_id(self, with_cppstd, settings_values=None):
        # Create the conanfile with corresponding settings
        settings = ["os", "compiler", ]
        if with_cppstd:
            settings += ["cppstd"]
        conanfile = self.conanfile.format(settings='", "'.join(settings))
        self.t.save({"conanfile.py": conanfile}, clean_first=True)

        # Create the string with the command line settings
        settings_values = settings_values or dict()
        settings_values_str = ["-s {k}={v}".format(k=k, v=v) for k, v in settings_values.items()]
        settings_values_str = " ".join(settings_values_str)

        # Call `conan info`
        json_file = os.path.join(self.t.current_folder, "tmp.json")
        self.t.run('info . {} --json="{}"'.format(settings_values_str, json_file))
        info_output = self.t.out
        data = json.loads(load(json_file))
        self.assertEqual(len(data), 1)

        # Return: ID, output
        return data[0]["id"], info_output

    def test_no_value(self):
        # No value passed for setting 'cppstd'
        id_with, output = self._get_id(with_cppstd=True)  # TODO: Should raise?
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertEqual(self.target_id, id_with)

    def test_value_none(self):
        # Explicit value 'None' passed to setting 'cppstd'
        id_with, output = self._get_id(with_cppstd=True, settings_values={"cppstd": "None"})
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertEqual(self.target_id, id_with)

    def test_value_default(self):
        # Explicit value (equals to default) passed to setting 'cppstd'
        cppstd = cppstd_default(self.compiler, self.compiler_version)
        id_with, output = self._get_id(with_cppstd=True, settings_values={"cppstd": cppstd})
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: gnu14", output)
        self.assertEqual(self.target_id, id_with)

    def test_value_other(self):
        # Explicit value (not the default) passed to setting 'cppstd'
        id_with, output = self._get_id(with_cppstd=True, settings_values={"cppstd": "14"})
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: 14", output)
        self.assertNotEqual(self.target_id, id_with)

