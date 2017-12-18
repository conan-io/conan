import os
import unittest

from conans.client.build.meson import Meson
from conans.client.conf import default_settings_yml
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.build_helpers.cmake_test import ConanFileMock


class MesonTest(unittest.TestCase):

    def folders_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        conan_file = ConanFileMock()
        conan_file.settings = settings
        conan_file.source_folder = "my_cache_source_folder"
        conan_file.build_folder = "my_cache_build_folder"
        meson = Meson(conan_file)
        meson.configure(source_dir="../subdir", build_dir="build")
        self.assertEquals(conan_file.command,
                          'meson "../subdir" "build" --backend=ninja --buildtype=release')

        meson.configure(build_dir="build")
        self.assertEquals(conan_file.command,
                          'meson "my_cache_source_folder" "build" '
                          '--backend=ninja --buildtype=release')

        meson.configure()
        self.assertEquals(conan_file.command,
                          'meson "my_cache_source_folder" '
                          '"my_cache_build_folder" --backend=ninja --buildtype=release')

        meson.configure(source_folder="source", build_folder="build")
        build_expected = os.path.join("my_cache_build_folder", "build")
        source_expected = os.path.join("my_cache_source_folder", "source")
        self.assertEquals(conan_file.command,
                          'meson "%s" "%s" --backend=ninja '
                          '--buildtype=release' % (source_expected, build_expected))

        conan_file.in_local_cache = True
        meson.configure(source_folder="source", build_folder="build",
                        cache_build_folder="rel_only_cache")
        build_expected = os.path.join("my_cache_build_folder", "rel_only_cache")
        source_expected = os.path.join("my_cache_source_folder", "source")
        self.assertEquals(conan_file.command,
                          'meson "%s" "%s" --backend=ninja '
                          '--buildtype=release' % (source_expected, build_expected))

        conan_file.in_local_cache = False
        meson.configure(source_folder="source", build_folder="build",
                        cache_build_folder="rel_only_cache")
        build_expected = os.path.join("my_cache_build_folder", "build")
        source_expected = os.path.join("my_cache_source_folder", "source")
        self.assertEquals(conan_file.command,
                          'meson "%s" "%s" --backend=ninja '
                          '--buildtype=release' % (source_expected, build_expected))

        conan_file.in_local_cache = True
        meson.configure(build_dir="build", cache_build_folder="rel_only_cache")
        build_expected = os.path.join("my_cache_build_folder", "rel_only_cache")
        source_expected = "my_cache_source_folder"
        self.assertEquals(conan_file.command,
                          'meson "%s" "%s" --backend=ninja '
                          '--buildtype=release' % (source_expected, build_expected))
        # Raise mixing
        with self.assertRaisesRegexp(ConanException, "Use 'build_folder'/'source_folder'"):
            meson.configure(source_folder="source", build_dir="build")
