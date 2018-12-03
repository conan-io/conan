import os
import shutil
import unittest

from conans.client import defs_to_string
from conans.client.build.meson import Meson
from conans.client.conf import default_settings_yml
from conans.client.tools import args_to_string
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.build_helpers.cmake_test import ConanFileMock
from conans.test.utils.test_files import temp_folder


class MesonTest(unittest.TestCase):

    def setUp(self):
        self.tempdir = temp_folder(path_with_spaces=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _check_commands(self, cmd_ref, cmd_test):
        cmd_ref_splitted = cmd_ref.split(' ')
        cmd_test_splitted = cmd_test.split(' ')
        self.assertEquals(cmd_ref_splitted[:3], cmd_test_splitted[:3])
        self.assertEquals(set(cmd_ref_splitted[3:]), set(cmd_test_splitted[3:]))

    def partial_build_test(self):
        conan_file = ConanFileMock()
        conan_file.settings = Settings()
        conan_file.should_configure = False
        conan_file.should_build = False
        conan_file.package_folder = os.path.join(self.tempdir, "my_cache_package_folder")
        meson = Meson(conan_file)
        meson.configure()
        self.assertIsNone(conan_file.command)
        meson.build()
        self.assertIsNone(conan_file.command)
        meson.test()
        self.assertIsNone(conan_file.command)
        meson.install()
        self.assertIsNone(conan_file.command)

    def folders_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        package_folder = os.path.join(self.tempdir, "my_cache_package_folder")
        conan_file = ConanFileMock()
        conan_file.settings = settings
        conan_file.source_folder = os.path.join(self.tempdir, "my_cache_source_folder")
        conan_file.build_folder = os.path.join(self.tempdir, "my_cache_build_folder")
        conan_file.package_folder = package_folder
        meson = Meson(conan_file)

        defs = {
            'default-library': 'shared',
            'prefix': package_folder,
            'cpp_std': 'none'
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
        defs['default-library'] = 'static'
        meson.configure(source_folder="source", build_folder="build", args=args,
                        defs={'default-library': 'static'})
        build_expected = os.path.join(self.tempdir, "my_cache_build_folder", "build")
        source_expected = os.path.join(self.tempdir, "my_cache_source_folder", "source")
        cmd_expected = 'meson "%s" "%s" --backend=ninja %s %s --buildtype=release' \
                       % (source_expected, build_expected, args_to_string(args), defs_to_string(defs))
        self._check_commands(cmd_expected, conan_file.command)

        # Raise mixing
        with self.assertRaisesRegexp(ConanException, "Use 'build_folder'/'source_folder'"):
            meson.configure(source_folder="source", build_dir="build")

        meson.test()
        self.assertEquals("ninja -C \"%s\" %s" % (build_expected, args_to_string(["test"])), conan_file.command)

        meson.install()
        self.assertEquals("ninja -C \"%s\" %s" % (build_expected, args_to_string(["install"])), conan_file.command)
