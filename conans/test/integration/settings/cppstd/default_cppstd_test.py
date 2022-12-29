# coding=utf-8

import json
import os
import textwrap
import unittest

from conans.client.build.cppstd_flags import cppstd_default
from conans.client.conf import get_default_settings_yml
from conans.client.tools import environment_append, save, load
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class DefaultCppTestCase(unittest.TestCase):
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
                compiler_cppstd = self.settings.get_safe("compiler.cppstd")
                self.output.info(">>>> settings: {{}}".format(self.settings.fields))
                self.output.info(">>>> cppstd: {{}}".format(cppstd))
                self.output.info(">>>> compiler.cppstd: {{}}".format(compiler_cppstd))
        """)

    id_default = "d17189cfe7b11efbc5d701339a32d203745f8b81"

    def run(self, *args, **kwargs):
        default_profile_path = os.path.join(temp_folder(), "default.profile")
        save(default_profile_path, self.default_profile)
        with environment_append({"CONAN_DEFAULT_PROFILE_PATH": default_profile_path}):
            super(DefaultCppTestCase, self).run(*args, **kwargs)

    def setUp(self):
        self.t = TestClient()
        # Compute ID without the setting 'cppstd'
        target_id, output = self._get_id(with_cppstd=False)
        self.assertEqual(target_id, self.id_default)
        self.assertIn(">>>> settings: ['compiler', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertIn(">>>> compiler.cppstd: None", output)

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

        # Return ID, output
        return data[0]["id"], info_output


def _make_cppstd_default(compiler, compiler_version):
    settings = Settings.loads(get_default_settings_yml())
    settings.compiler = compiler
    settings.compiler.version = compiler_version
    return cppstd_default(settings)


class SettingsCppStdTests(DefaultCppTestCase):
    """
    Validate package ID computed taking into account different scenarios for 'cppstd'. The ID
    should be the same if the setting is not provided and if it has the default value.
    """

    def test_no_value(self):
        # No value passed for setting 'cppstd'
        id_with, output = self._get_id(with_cppstd=True)  # TODO: Should raise?
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertIn(">>>> compiler.cppstd: None", output)
        self.assertEqual(self.id_default, id_with)

    def test_value_none(self):
        # Explicit value 'None' passed to setting 'cppstd'
        id_with, output = self._get_id(with_cppstd=True, settings_values={"cppstd": "None"})
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertIn(">>>> compiler.cppstd: None", output)
        self.assertEqual(self.id_default, id_with)

    def test_value_default(self):
        # Explicit value (equals to default) passed to setting 'cppstd'
        cppstd = _make_cppstd_default(self.compiler, self.compiler_version)
        id_with, output = self._get_id(with_cppstd=True, settings_values={"cppstd": cppstd})
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: gnu14", output)
        self.assertIn(">>>> compiler.cppstd: None", output)
        self.assertEqual(self.id_default, id_with)

    def test_value_non_default(self):
        # Explicit value (not the default) passed to setting 'cppstd'
        id_with, output = self._get_id(with_cppstd=True, settings_values={"cppstd": "14"})
        self.assertIn(">>>> settings: ['compiler', 'cppstd', 'os']", output)
        self.assertIn(">>>> cppstd: 14", output)
        self.assertIn(">>>> compiler.cppstd: None", output)
        self.assertNotEqual(self.id_default, id_with)


class SettingsCompilerCppStdTests(DefaultCppTestCase):
    """
    Validate package ID computed taking into account different scenarios for 'compiler.cppstd'. The
    ID has to be the same if the setting is not informed and if it has the default value, also
    these values should be the same as the ones using the 'cppstd' approach.
    """

    def _get_id(self, with_cppstd=False, settings_values=None):
        assert not with_cppstd
        return super(SettingsCompilerCppStdTests, self)._get_id(with_cppstd=False,
                                                                settings_values=settings_values)

    def test_value_none(self):
        # Explicit value 'None' passed to setting 'cppstd'
        id_with, output = self._get_id(settings_values={"compiler.cppstd": "None"})
        self.assertIn(">>>> settings: ['compiler', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertIn(">>>> compiler.cppstd: None", output)
        self.assertEqual(self.id_default, id_with)

    def test_value_default(self):
        # Explicit value (equals to default) passed to setting 'compiler.cppstd'
        cppstd = _make_cppstd_default(self.compiler, self.compiler_version)
        id_with, output = self._get_id(settings_values={"compiler.cppstd": cppstd})
        self.assertIn(">>>> settings: ['compiler', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertIn(">>>> compiler.cppstd: gnu14", output)
        self.assertEqual(self.id_default, id_with)

    def test_value_other(self):
        # Explicit value (not the default) passed to setting 'cppstd'
        id_with, output = self._get_id(settings_values={"compiler.cppstd": "14"})
        self.assertIn(">>>> settings: ['compiler', 'os']", output)
        self.assertIn(">>>> cppstd: None", output)
        self.assertIn(">>>> compiler.cppstd: 14", output)
        self.assertNotEqual(self.id_default, id_with)


class SettingsCompareCppStdApproaches(DefaultCppTestCase):
    """
    Check scenario using 'cppstd' and 'compiler.cppstd', if those are given the same value
    (but different from the default one) then the ID for the packages is not required to be
    the same.
    """

    def test_cppstd_non_defaults(self):
        cppstd_value = "14"  # Not the default
        id_with_old, _ = self._get_id(with_cppstd=True, settings_values={"cppstd": cppstd_value})
        id_with_new, _ = self._get_id(with_cppstd=False,
                                      settings_values={'compiler.cppstd': cppstd_value})

        # Those are different from the target one (ID using default value or None)
        self.assertNotEqual(self.id_default, id_with_old)
        self.assertNotEqual(self.id_default, id_with_new)

        # They are different between them
        self.assertNotEqual(id_with_new, id_with_old)
