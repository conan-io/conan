# coding=utf-8

import os
import re
import textwrap
import unittest

from conans.model.editable_layout import LAYOUTS_FOLDER
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save_files, save


class LayoutTest(unittest.TestCase):

    def test_editable_crash(self):
        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        client = TestClient()
        layout = textwrap.dedent("""
                    [build_folder]
                    build
                    """)
        client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0"),
                     "mylayout": layout})
        client.run("editable add . {} --layout mylayout".format(ref))
        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile().with_name("app").with_version("1.0")
                                                    .with_require(ref)})
        client2.run("create . user/testing")
        graph_info = os.path.join(client.current_folder, "build", "graph_info.json")
        self.assertTrue(os.path.exists(graph_info))

    def test_missing_wrong_layouts(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)

        client.save({"conanfile.py": conanfile,
                     "layout": ""})
        client.run("editable add . mytool/0.1@user/testing -l=layout")
        self.assertIn("Using layout file:", client.out)
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client.save({"conanfile.py": conanfile,
                     "layout": " some garbage"})
        client2.save({"conanfile.txt": consumer})
        client2.run("install .", assert_error=True)
        self.assertIn("ERROR: Error parsing layout file", client2.out)
        self.assertIn("File contains no section headers.", client2.out)
        self.assertIn("line: 1", client2.out)

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
        layout_folder = os.path.join(client.cache_folder, LAYOUTS_FOLDER)
        ref_str = "mytool/0.1@user/testing"
        save_files(layout_folder, {"layout_win_cache": layout_cache.format(ref_str, "win_cache"),
                                   "layout_linux_cache": layout_cache.format(ref_str,
                                                                             "linux_cache"),
                                   "layout_win_cache2": layout_repo.format("win_cache2"),
                                   "layout_linux_cache2": layout_repo.format("linux_cache2")})
        client.save({"conanfile.py": conanfile,
                     "layout_win": layout_repo.format("win"),
                     "layout_linux": layout_repo.format("linux")})
        client.run("editable add . mytool/0.1@user/testing")
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake")
        self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
        cmake = client2.load("conanbuildinfo.cmake")
        include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
        self.assertTrue(include_dirs.endswith("include"))

        # Using the repo file layouts
        for layout in ("win", "linux", "win_cache", "linux_cache", "win_cache2", "linux_cache2"):
            client.run("editable add . mytool/0.1@user/testing -l=layout_%s" % layout)
            client2.run("install . -g cmake")
            self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
            cmake = client2.load("conanbuildinfo.cmake")
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

        layout_folder = os.path.join(client.cache_folder, LAYOUTS_FOLDER)
        save_files(layout_folder, {"win/cache": layout_repo.format("win/cache"),
                                   "linux/cache": layout_repo.format("linux/cache")})
        client.save({"conanfile.py": conanfile,
                     "layout/win": layout_repo.format("layout/win"),
                     "layout/linux": layout_repo.format("layout/linux")})
        client.run("editable add . mytool/0.1@user/testing")
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake")
        self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
        cmake = client2.load("conanbuildinfo.cmake")
        include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
        self.assertTrue(include_dirs.endswith("include"))

        # Using the cache file layouts
        for layout in ("win/cache", "linux/cache", "layout/win", "layout/linux"):
            client.run("editable add . mytool/0.1@user/testing -l=%s" % layout)
            client2.run("install . -g cmake")
            self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
            cmake = client2.load("conanbuildinfo.cmake")
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
        client.run("editable add . mytool/0.1@user/testing")
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})

        for build_type in ("Debug", "Release"):
            client2.run("install . -s build_type=%s -g cmake" % build_type)
            self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
            cmake = client2.load("conanbuildinfo.cmake")
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % build_type.lower()))

    def test_develop(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def package_info(self):
                    if not self.in_local_cache:
                        self.output.info("Develop!!=%s!!" % self.develop)
            """)

        client.save({"conanfile.py": conanfile})
        client.run("editable add . mytool/0.1@user/testing")
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install .")
        self.assertIn("mytool/0.1@user/testing: Develop!!=True!!", client2.out)

    def test_parameterized_paths(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)
        layout_repo = textwrap.dedent("""
            [includedirs]
            include_{{settings.build_type}}
            """)

        client.save({"conanfile.py": conanfile,
                     "layout": layout_repo})
        client.run("editable add . mytool/0.1@user/testing -l=layout")
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake -s build_type=Debug", assert_error=True)
        self.assertIn("ERROR: Error parsing layout file '{}' (for reference "
                      "'mytool/0.1@user/testing')\n'settings.build_type' doesn't exist".format(
                          os.path.join(client.current_folder, 'layout')),
                      client2.out)

        # Now add settings to conanfile
        client.save({"conanfile.py": conanfile.replace("pass", 'settings = "build_type"')})
        for setting in ("Debug", "Release"):
            client2.run("install . -g cmake -s build_type=%s" % setting)
            self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
            cmake = client2.load("conanbuildinfo.cmake")
            include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
            self.assertTrue(include_dirs.endswith("include_%s" % setting))

    def test_absolute_paths(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
            """)
        layoutabs = textwrap.dedent("""
            [includedirs]
            include_abs_path
            """)

        tmp_folder = temp_folder()
        layout_path = os.path.join(tmp_folder, "layout")
        save(layout_path, layoutabs)
        client.save({"conanfile.py": conanfile})
        client.run('editable add . mytool/0.1@user/testing -l="%s"' % layout_path)
        client2 = TestClient(client.cache_folder)
        consumer = textwrap.dedent("""
            [requires]
            mytool/0.1@user/testing
            """)
        client2.save({"conanfile.txt": consumer})
        client2.run("install . -g cmake")
        self.assertIn("mytool/0.1@user/testing from user folder - Editable", client2.out)
        cmake = client2.load("conanbuildinfo.cmake")
        include_dirs = re.search('set\(CONAN_INCLUDE_DIRS_MYTOOL "(.*)"\)', cmake).group(1)
        self.assertTrue(include_dirs.endswith("include_abs_path"))
