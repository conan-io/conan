# coding=utf-8

import os
import re
import textwrap
import unittest

from conans.test.utils.tools import TestClient
from conans.util.files import load, save_files
from conans.model.editable_cpp_info import LAYOUTS_FOLDER


class LayoutTest(unittest.TestCase):

    def test_missing_wrong_layouts(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)

        client.save({"conanfile.py": conanfile,
                     "layout": ""})
        client.run("link . mytool/0.1@user/testing -l=layout")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client.save({"conanfile.py": conanfile,
                     "layout": " some garbage"})
        client2.save({"conanfile.txt": consumer})
        client2.run("install .", assert_error=True)
        self.assertIn("ERROR: Error parsing layout file", client2.out)

        client.save({"conanfile.py": conanfile}, clean_first=True)
        client2.run("install .", assert_error=True)
        self.assertIn("ERROR: Layout file not found", client2.out)

    def test_repo_layouts(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)
        layout_repo = textwrap.dedent("""
            [includedirs]
            include_{}
            """)
        layout_cache = textwrap.dedent("""
            [{}:includedirs]
            include_{}
            """)
        layout_folder = os.path.join(client.base_folder, ".conan", LAYOUTS_FOLDER)
        save_files(layout_folder, {"layout_win_cache": layout_cache.format("mytool", "win_cache"),
                                   "layout_linux_cache": layout_cache.format("mytool",
                                                                             "linux_cache"),
                                   "layout_win_cache2": layout_repo.format("win_cache2"),
                                   "layout_linux_cache2": layout_repo.format("linux_cache2")})
        client.save({"conanfile.py": conanfile,
                     "layout_win": layout_repo.format("win"),
                     "layout_linux": layout_repo.format("linux")})
        client.run("link . mytool/0.1@user/testing")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake")
        self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
        cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
        include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
        self.assertTrue(include_dirs.endswith("include"))

        # Using the repo file layouts
        for layout in ("win", "linux", "win_cache", "linux_cache", "win_cache2", "linux_cache2"):
            client.run("link . mytool/0.1@user/testing -l=layout_%s" % layout)
            client2.run("install . -g cmake")
            self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
            cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % layout))

    def test_layouts_files_paths(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)
        layout_repo = textwrap.dedent("""
            [includedirs]
            include_{}
            """)

        layout_folder = os.path.join(client.base_folder, ".conan", LAYOUTS_FOLDER)
        save_files(layout_folder, {"win/cache": layout_repo.format("win/cache"),
                                   "linux/cache": layout_repo.format("linux/cache")})
        client.save({"conanfile.py": conanfile,
                     "layout/win": layout_repo.format("layout/win"),
                     "layout/linux": layout_repo.format("layout/linux")})
        client.run("link . mytool/0.1@user/testing")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake")
        self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
        cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
        include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
        self.assertTrue(include_dirs.endswith("include"))

        # Using the cache file layouts
        for layout in ("win/cache", "linux/cache", "layout/win", "layout/linux"):
            client.run("link . mytool/0.1@user/testing -l=%s" % layout)
            client2.run("install . -g cmake")
            self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
            cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % layout))

    def test_recipe_paths(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "build_type"
                def package_info(self):
                    if not self.in_local_cache:
                        d = "include_%s" % self.settings.build_type
                        self.cpp_info.includedirs = [d.lower()]
            """)

        client.save({"conanfile.py": conanfile})
        client.run("link . mytool/0.1@user/testing")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})

        for build_type in ("Debug", "Release"):
            client2.run("install . -s build_type=%s -g cmake" % build_type)
            self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
            cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % build_type.lower()))

    def test_parameterized_paths(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)
        layout_repo = textwrap.dedent("""
            [includedirs]
            include_{settings.build_type}
            """)

        client.save({"conanfile.py": conanfile,
                     "layout": layout_repo})
        client.run("link . mytool/0.1@user/testing -l=layout")
        client2 = TestClient(client.base_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake -s build_type=Debug", assert_error=True)
        self.assertIn("ERROR: Error applying layout in 'mytool': "
                      "'settings.build_type' doesn't exist", client2.out)

        # Now add settings to conanfile
        client.save({"conanfile.py": conanfile.replace("pass", 'settings = "build_type"')})
        for setting in ("Debug", "Release"):
            client2.run("install . -g cmake -s build_type=%s" % setting)
            self.assertIn("mytool/0.1@user/testing from local cache - Editable", client2.out)
            cmake = load(os.path.join(client2.current_folder, "conanbuildinfo.cmake"))
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % setting))
