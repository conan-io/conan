import os
import shutil
import unittest
from parameterized.parameterized import parameterized

import six

from conans.client.build import defs_to_string
from conans.client.build.meson import Meson
from conans.client.conf import get_default_settings_yml
from conans.client.tools import args_to_string, environment_append
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.model.settings import Settings
from conans.test.utils.mocks import MockDepsCppInfo, ConanFileMock
from conans.test.utils.test_files import temp_folder


class MesonTest(unittest.TestCase):

    def setUp(self):
        self.tempdir = temp_folder(path_with_spaces=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _check_commands(self, cmd_ref, cmd_test):
        cmd_ref_splitted = cmd_ref.split(' ')
        cmd_test_splitted = cmd_test.split(' ')
        self.assertEqual(cmd_ref_splitted[:3], cmd_test_splitted[:3])
        self.assertEqual(set(cmd_ref_splitted[3:]), set(cmd_test_splitted[3:]))

    def test_partial_build(self):
        conan_file = ConanFileMock()
        conan_file.settings = Settings()
        conan_file.should_configure = False
        conan_file.should_build = False
        conan_file.should_test = False
        conan_file.should_install = False
        conan_file.folders.set_base_package(os.path.join(self.tempdir, "my_cache_package_folder"))
        meson = Meson(conan_file)
        meson.configure()
        self.assertIsNone(conan_file.command)
        meson.build()
        self.assertIsNone(conan_file.command)
        meson.test()
        self.assertIsNone(conan_file.command)
        meson.install()
        self.assertIsNone(conan_file.command)
        meson.meson_test()
        self.assertIsNone(conan_file.command)
        meson.meson_install()
        self.assertIsNone(conan_file.command)

    def test_conan_run_tests(self):
        conan_file = ConanFileMock()
        conan_file.settings = Settings()
        conan_file.should_test = True
        meson = Meson(conan_file)
        with environment_append({"CONAN_RUN_TESTS": "0"}):
            meson.test()
            self.assertIsNone(conan_file.command)

    def test_conf_skip_test(self):
        conf = ConfDefinition()
        conf.loads("tools.build:skip_test=1")
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        conanfile.conf = conf.get_conanfile_conf(None)
        meson = Meson(conanfile)
        meson.test()
        self.assertIsNone(conanfile.command)

    def test_folders(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        package_folder = os.path.join(self.tempdir, "my_cache_package_folder")
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = MockDepsCppInfo()
        conan_file.settings = settings
        conan_file.folders.set_base_source(os.path.join(self.tempdir, "my_cache_source_folder"))
        conan_file.folders.set_base_build(os.path.join(self.tempdir, "my_cache_build_folder"))
        conan_file.folders.set_base_package(package_folder)
        meson = Meson(conan_file)

        defs = {
            'default_library': 'shared',
            'prefix': package_folder,
            'libdir': 'lib',
            'bindir': 'bin',
            'sbindir': 'bin',
            'libexecdir': 'bin',
            'includedir': 'include'
        }

        meson.configure(source_dir=os.path.join(self.tempdir, "../subdir"),
                        build_dir=os.path.join(self.tempdir, "build"))
        source_expected = os.path.join(self.tempdir, "../subdir")
        build_expected = os.path.join(self.tempdir, "build")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        meson.configure(build_dir=os.path.join(self.tempdir, "build"))
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder")
        build_expected = os.path.join(self.tempdir, "build")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        meson.configure()
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder")
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        meson.configure(source_folder="source", build_folder="build")
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder", "build")
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder", "source")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        conan_file.in_local_cache = True
        meson.configure(source_folder="source", build_folder="build",
                        cache_build_folder="rel_only_cache")
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder", "rel_only_cache")
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder", "source")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        conan_file.in_local_cache = False
        meson.configure(source_folder="source", build_folder="build",
                        cache_build_folder="rel_only_cache")
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder", "build")
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder", "source")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        conan_file.in_local_cache = True
        meson.configure(build_dir="build", cache_build_folder="rel_only_cache")
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder", "rel_only_cache")
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s --buildtype=release' \
                       % (source_expected, build_expected, defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        args = ['--werror', '--warnlevel 3']
        defs['default_library'] = 'static'
        meson.configure(source_folder="source", build_folder="build", args=args,
                        defs={'default_library': 'static'})
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder", "build")
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder", "source")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s %s --buildtype=release' \
                       % (source_expected, build_expected, args_to_string(args),
                          defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        # Raise mixing
        with six.assertRaisesRegex(self, ConanException, "Use 'build_folder'/'source_folder'"):
            meson.configure(source_folder="source", build_dir="build")

        meson.test()
        self.assertEqual("ninja -C \"%s\" %s" % (build_expected, args_to_string(["test"])),
                         conan_file.command)

        meson.install()
        self.assertEqual("ninja -C \"%s\" %s" % (build_expected, args_to_string(["install"])),
                         conan_file.command)

        meson.meson_test()
        self.assertEqual("meson test -C \"%s\"" % build_expected,
                         conan_file.command)

        meson.meson_install()
        self.assertEqual("meson install -C \"%s\"" % build_expected,
                         conan_file.command)

    def test_other_backend(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = MockDepsCppInfo()
        conan_file.settings = Settings()
        conan_file.folders.set_base_package(os.getcwd())
        meson = Meson(conan_file, backend="vs")
        meson.configure()
        self.assertIn("--backend=vs", conan_file.command)
        meson.build()
        self.assertIn("meson compile -C", conan_file.command)
        meson.install()
        self.assertIn("meson compile -C", conan_file.command)
        meson.test()
        self.assertIn("meson compile -C", conan_file.command)

    def test_prefix(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = MockDepsCppInfo()
        conan_file.settings = Settings()
        conan_file.folders.set_base_package(os.getcwd())
        expected_prefix = '-Dprefix="%s"' % os.getcwd()
        meson = Meson(conan_file)
        meson.configure()
        self.assertIn(expected_prefix, conan_file.command)
        meson.build()
        self.assertIn("ninja -C", conan_file.command)
        meson.install()
        self.assertIn("ninja -C", conan_file.command)

    def test_no_prefix(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = MockDepsCppInfo()
        conan_file.settings = Settings()
        meson = Meson(conan_file)
        meson.configure()
        self.assertNotIn('-Dprefix', conan_file.command)
        meson.build()
        self.assertIn("ninja -C", conan_file.command)
        with self.assertRaises(TypeError):
            meson.install()

    @parameterized.expand([('Linux', 'gcc', '6.3', 'x86', None, '-m32'),
                           ('Linux', 'gcc', '6.3', 'x86_64', None, '-m64'),
                           ('Windows', 'Visual Studio', '15', 'x86', 'MD', '-MD')])
    def test_flags_applied(self, the_os, compiler, version, arch, runtime, flag):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = the_os
        settings.compiler = compiler
        settings.compiler.version = version
        settings.arch = arch
        if runtime:
            settings.compiler.runtime = runtime
        settings.build_type = "Release"
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = MockDepsCppInfo()
        conan_file.settings = settings
        meson = Meson(conan_file)
        meson.configure()
        meson.build()
        self.assertIn(flag, conan_file.captured_env["CFLAGS"])
        self.assertIn(flag, conan_file.captured_env["CXXFLAGS"])
