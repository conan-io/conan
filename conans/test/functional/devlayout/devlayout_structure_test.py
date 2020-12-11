import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TurboTestClient, GenConanfile


class DevLayoutNoBuildTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools
            from conan.tools.layout import DefaultLayout

            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "cmake"

                {}

                def source(self):
                    # Generate a fake source, in an "unzipped-folder"
                    self.output.warn("CURDIR: %s" % os.getcwd())
                    assert "unzipped-folder" in os.getcwd(), "curdir is not correctly changed"
                    tools.save("hello.cpp", "foo")
                    tools.save("hello.h", "foo")
                    tools.save(os.path.join("custom-include", "custom.h"), "foo")

                def build(self):
                    # We have access to sources
                    self.output.warn("CURDIR: %s" % os.getcwd())
                    self.output.warn("self.build_folder: %s" % self.build_folder)
                    self.output.warn("self.source_folder: %s" % self.source_folder)
                    assert "build-folder" in os.getcwd(), "curdir is not correctly changed"

                    assert os.path.exists(os.path.join(self.source_folder, "hello.cpp"))

                    # We fake building something, this would be usually done by the build helper
                    # automatically

                    tools.save(os.path.join(self.lyt.build_libdir, "hello.a"), "foo")
                    tools.save(os.path.join("include", "generated_header.h"), "foo")
                    tools.save(os.path.join(self.lyt.build_bindir, "myapp.exe"), "foo")

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
        lyt.install = "install-folder"

        lyt.src_includedirs = ["custom-include"]
        lyt.src_resdir = "my_src_resdir"
        lyt.src_builddir = "my_src_builddir"

        lyt.build_libdir = "my_libdir"
        lyt.build_bindir = "my_bindir"
        lyt.build_includedirs = ["include"]
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
        install_f = os.path.join(client.current_folder, "install-folder")
        bf = os.path.join(client.current_folder, "build-folder")
        sf = os.path.join(client.current_folder, "unzipped-folder")
        client.run("install .")
        self.assertTrue(os.path.exists(install_f))
        client.run("source .")
        self.assertTrue(os.path.exists(sf))
        client.run("build . -if=install-folder")
        self.assertTrue(os.path.exists(os.path.join(install_f, "conaninfo.txt")))
        self.assertTrue(os.path.exists(os.path.join(bf, "my_libdir", "hello.a")))
        self.assertTrue(os.path.exists(os.path.join(bf, "my_bindir", "myapp.exe")))
        client.run("package . -if=install-folder")
        pf = os.path.join(client.current_folder, "package")
        self.assertTrue(os.path.exists(os.path.join(pf, "other_lib", "hello.a")))
        # The hello.h is not packaged because / is not included as include dir
        self.assertTrue(os.path.exists(os.path.join(pf, "other_bin", "myapp.exe")))
        self.assertFalse(os.path.exists(os.path.join(pf, "other_include", "hello.h")))
        self.assertTrue(os.path.exists(os.path.join(pf, "other_include", "custom.h")))

        # Now make it editable and create a consumer for it
        client.run("editable add . lib/1.0@")
        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile().with_requirement("lib/1.0")})
        client2.run("install .")
        txt_contents = client2.load("conanbuildinfo.txt").replace("\r\n", "\n")
        # Verify everything points to the correct build layout
        curfolder = client.current_folder.replace("\\", "/")

        expected = """[includedirs]
{path}/build-folder/include
{path}/unzipped-folder/custom-include

[libdirs]
{path}/build-folder/my_libdir

[bindirs]
{path}/build-folder/my_bindir

[resdirs]
{path}/build-folder/my_resdir
{path}/unzipped-folder/my_src_resdir

[builddirs]
{path}/build-folder/my_builddir
{path}/unzipped-folder/my_src_builddir"""

        self.assertIn(expected.format(path=curfolder), txt_contents)

        # Verify that the layout is kept in the cache
        client.run("editable remove lib/1.0@")
        ref = ConanFileReference.loads("lib/1.0@")
        pref = client.create(ref, conanfile=None)
        pl = client.cache.package_layout(pref.ref)
        # Check the build folder
        build_folder = os.path.join(pl.build(pref), "build-folder")
        install_folder = os.path.join(pl.build(pref), "install-folder")
        self.assertEqual(os.listdir(install_folder), ['conanbuildinfo.cmake'])
        libs_dir = os.path.join(build_folder, "my_libdir")
        self.assertEqual(os.listdir(libs_dir), ['hello.a'])
        bin_dir = os.path.join(build_folder, "my_bindir")
        self.assertEqual(os.listdir(bin_dir), ['myapp.exe'])
        # Check the package folder
        p_folder = pl.package(pref)
        self.assertEqual(set(os.listdir(os.path.join(p_folder))),
                         {'conaninfo.txt', 'conanmanifest.txt', 'other_bin', 'other_build',
                          'other_include', 'other_lib', 'other_resdir'})
        include_dir = os.path.join(p_folder, "other_include")
        self.assertEqual(set(os.listdir(include_dir)), {'custom.h', 'generated_header.h'})
        bin_dir = os.path.join(p_folder, "other_bin")
        self.assertEqual(os.listdir(bin_dir), ['myapp.exe'])
        build_dir = os.path.join(p_folder, "other_build")
        self.assertEqual(os.listdir(build_dir), ['script.cmake'])
        res_dir = os.path.join(p_folder, "other_resdir")
        self.assertEqual(os.listdir(res_dir), ['doraemon.jpg'])
        lib_dir = os.path.join(p_folder, "other_lib")
        self.assertEqual(os.listdir(lib_dir), ['hello.a'])

