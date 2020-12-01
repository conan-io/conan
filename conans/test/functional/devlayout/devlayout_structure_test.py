import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TurboTestClient, GenConanfile


class DevLayoutNoBuildTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools, DefaultLayout

            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "cmake"

                {}

                def source(self):
                    # Generate a fake source, in an "unzipped-folder"
                    tools.save(os.path.join("unzipped-folder", "hello.cpp"), "foo")
                    tools.save(os.path.join("unzipped-folder", "hello.h"), "foo")

                def build(self):
                    # We have access to sources
                    assert os.path.exists(os.path.join(self.lyt.source_folder, "hello.cpp"))

                    # We fake building something, this would be usually done by the build helper
                    # automatically
                    tools.save(os.path.join(self.lyt.build_lib_folder, "hello.a"), "foo")
                    tools.save(os.path.join("include", "generated_header.h"), "foo")
                    tools.save(os.path.join(self.lyt.build_bin_folder, "myapp.exe"), "foo")

                    # Some build assets and resources
                    tools.save(os.path.join(self.lyt.build_builddir, "script.cmake"), "foo")
                    tools.save(os.path.join(self.lyt.build_resdir, "doraemon.jpg"), "foo")

                def package(self):
                    self.lyt.package(build_patterns=["script.cmake"],
                                     res_patterns=["doraemon.jpg"])

                def package_info(self):
                    self.lyt.package_info()
                    self.cpp_info.libs = ["hello"]
                """)

    def test_everything_match(self):
        layout = """
    def layout(self):
        lyt = DefaultLayout(self)
        lyt.src = "unzipped-folder"
        lyt.build = "build-folder"
        lyt.build_libdir = "my_libdir"
        lyt.build_bindir = "my_bindir"
        lyt.build_includedirs = [lyt.src, "{}/include".format(lyt.build)]
        lyt.build_resdir = "my_resdir"
        lyt.build_builddir = "my_builddir"

        lyt.pkg_libdir = "other_lib"
        lyt.pkg_bindir = "other_bin"
        lyt.pkg_includedir = "other_include"
        lyt.pkg_builddir = "other_build"
        lyt.pkg_resdir = "other_resdir"

        self.lyt = lyt
"""
        client = TurboTestClient()
        client.save({"conanfile.py": self.conanfile.format(layout)})

        # First check the local methods
        bf = os.path.join(client.current_folder, "build-folder")
        sf = os.path.join(client.current_folder, "unzipped-folder")
        client.run("install .")
        self.assertTrue(os.path.exists(bf))
        client.run("source .")
        self.assertTrue(os.path.exists(sf))
        client.run("build . -if=build-folder")
        self.assertTrue(os.path.exists(os.path.join(bf, "conaninfo.txt")))
        self.assertTrue(os.path.exists(os.path.join(bf, "my_libdir", "hello.a")))
        self.assertTrue(os.path.exists(os.path.join(bf, "my_bindir", "myapp.exe")))
        client.run("package . -if=build-folder")
        pf = os.path.join(client.current_folder, "package")
        self.assertTrue(os.path.exists(os.path.join(pf, "other_lib", "hello.a")))
        self.assertTrue(os.path.exists(os.path.join(pf, "other_bin", "myapp.exe")))
        self.assertTrue(os.path.exists(os.path.join(pf, "other_include", "hello.h")))

        # Now make it editable and create a consumer for it
        client.run("editable add . lib/1.0@")
        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile().with_require_plain("lib/1.0")})
        client2.run("install .")
        txt_contents = client2.load("conanbuildinfo.txt").replace("\r\n", "\n")
        # Verify everything points to the correct build layout
        curfolder = client.current_folder.replace("\\", "/")
        includes_line = "[includedirs]\n" \
                        "{}/unzipped-folder\n" \
                        "{}/build-folder/include\n".format(curfolder, curfolder)
        self.assertIn(includes_line, txt_contents)
        libs_line = "[libdirs]\n{}/build-folder/my_libdir\n\n".format(curfolder)
        self.assertIn(libs_line, txt_contents)
        bins_line = "[bindirs]\n{}/build-folder/my_bindir\n\n".format(curfolder)
        self.assertIn(bins_line, txt_contents)
        res_line = "[resdirs]\n{}/my_resdir\n\n".format(curfolder)
        self.assertIn(res_line, txt_contents)
        builds_line = "[builddirs]\n{}/my_builddir\n\n".format(curfolder)
        self.assertIn(builds_line, txt_contents)

        # Verify that the layout is kept in the cache
        client.run("editable remove lib/1.0@")
        ref = ConanFileReference.loads("lib/1.0@")
        pref = client.create(ref, conanfile=None)
        pl = client.cache.package_layout(pref.ref)
        # Check the build folder
        build_folder = pl.build(pref)
        self.assertEqual(set(os.listdir(os.path.join(build_folder, "build-folder"))),
                         {'conanbuildinfo.cmake', 'my_bindir', 'my_libdir'})
        libs_dir = os.path.join(build_folder, "build-folder", "my_libdir")
        self.assertEqual(os.listdir(libs_dir), ['hello.a'])
        bin_dir = os.path.join(build_folder, "build-folder", "my_bindir")
        self.assertEqual(os.listdir(bin_dir), ['myapp.exe'])
        # Check the package folder
        p_folder = pl.package(pref)
        self.assertEqual(set(os.listdir(os.path.join(p_folder))),
                         {'conaninfo.txt', 'conanmanifest.txt', 'other_bin', 'other_build',
                          'other_include', 'other_lib', 'other_resdir'})
        include_dir = os.path.join(p_folder, "other_include")
        self.assertEqual(os.listdir(include_dir), ['hello.h'])
        bin_dir = os.path.join(p_folder, "other_bin")
        self.assertEqual(os.listdir(bin_dir), ['myapp.exe'])
        build_dir = os.path.join(p_folder, "other_build")
        self.assertEqual(os.listdir(build_dir), ['script.cmake'])
        res_dir = os.path.join(p_folder, "other_resdir")
        self.assertEqual(os.listdir(res_dir), ['doraemon.jpg'])
        lib_dir = os.path.join(p_folder, "other_lib")
        self.assertEqual(os.listdir(lib_dir), ['hello.a'])

