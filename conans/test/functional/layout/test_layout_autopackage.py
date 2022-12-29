import os
import re

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_auto_package_no_components():
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """

    def source(self):
        tools.save("source_sources/source_stuff.cpp", "")
        tools.save("source_includes/include1.hpp", "")
        tools.save("source_includes/include2.hpp", "")
        tools.save("source_includes2/include3.h", "")
        tools.save("source_libs/slibone.a", "")
        tools.save("source_libs/slibtwo.a", "")
        tools.save("source_libs/bin_to_discard.exe", "")
        tools.save("source_bins/source_bin.exe", "")
        tools.save("source_frameworks/sframe1/include/include.h", "")
        tools.save("source_frameworks/sframe2/include/include.h", "")
        tools.save("source_frameworks/sframe1/lib/libframework.lib", "")
        tools.save("source_frameworks/sframe2/lib/libframework.lib", "")
        tools.save("source_frameworks/sframe2/foo/bar.txt", "")

    def build(self):
        tools.save("build_sources/build_stuff.cpp", "")
        tools.save("build_sources/subdir/othersubdir/selective_stuff.cpp", "")
        tools.save("build_includes/include3.h", "")
        tools.save("build_includes/include4.hpp", "")
        tools.save("build_libs/blibone.a", "")
        tools.save("build_libs/blibtwo.a", "")
        tools.save("build_bins/build_bin.exe", "")
        tools.save("build_frameworks/bframe1/include/include.h", "")
        tools.save("build_frameworks/bframe2/include/include.h", "")


    def layout(self):

        self.folders.source = "my_source"
        self.folders.build = "my_build"
        self.folders.generators = "my_build/generators"

        # Package locations
        self.cpp.package.includedirs = ["my_includes"]
        self.cpp.package.srcdirs = ["my_sources"]
        self.cpp.package.bindirs = ["my_bins"]
        self.cpp.package.libdirs = ["my_libs"]
        self.cpp.package.frameworkdirs = ["my_frameworks"]

        # Source CPP INFO
        self.cpp.source.srcdirs = ["source_sources"]
        self.cpp.source.includedirs = ["source_includes", "source_includes2"]
        self.cpp.source.libdirs = ["source_libs"]
        self.cpp.source.bindirs = ["source_bins"]
        self.cpp.source.frameworkdirs = ["source_frameworks"]

        # Build CPP INFO
        self.cpp.build.srcdirs = ["build_sources",
                                              "build_sources/subdir/othersubdir"]
        self.cpp.build.includedirs = ["build_includes"]
        self.cpp.build.libdirs = ["build_libs"]
        self.cpp.build.bindirs = ["build_bins"]
        self.cpp.build.frameworkdirs = ["build_frameworks"]

    def package(self):
        # Discard include3.h from source
        packager = AutoPackager(self)
        packager.patterns.build.include = ["*.hpp", "*.h", "include3.h"]
        packager.patterns.build.lib = ["*.a"]
        packager.patterns.build.bin = ["*.exe"]
        packager.patterns.build.src = ["*.cpp"]
        packager.patterns.build.framework = ["sframe*", "bframe*"]
        packager.patterns.source.include = ["*.hpp"] # Discard include3.h from source
        packager.patterns.source.lib = ["*.a"]
        packager.patterns.source.bin = ["*.exe"]
        packager.patterns.source.src = ["*.cpp"]
        packager.patterns.source.framework = ["sframe*"]
        packager.run()
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    package_id = re.search(r"lib/1.0:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, package_id)
    p_folder = client.cache.package_layout(ref).package(pref)

    def p_path(path):
        return os.path.join(p_folder, path)

    # Check directories that shouldn't exist
    assert not os.path.exists(p_path("include"))
    assert not os.path.exists(p_path("bin"))
    assert not os.path.exists(p_path("lib"))

    # Check files source
    assert os.path.exists(p_path("my_sources"))
    assert os.path.exists(p_path("my_sources/source_stuff.cpp"))

    assert os.path.exists(p_path("my_includes/include1.hpp"))
    assert os.path.exists(p_path("my_includes/include2.hpp"))
    assert not os.path.exists(p_path("my_includes/include.h"))

    assert os.path.exists(p_path("my_libs/slibone.a"))
    assert os.path.exists(p_path("my_libs/slibtwo.a"))

    assert os.path.exists(p_path("my_bins/source_bin.exe"))
    assert not os.path.exists(p_path("my_bins/bin_to_discard.exe"))

    assert os.path.exists(p_path("my_frameworks/sframe1/include/include.h"))
    assert os.path.exists(p_path("my_frameworks/sframe2/include/include.h"))
    assert os.path.exists(p_path("my_frameworks/sframe1/lib/libframework.lib"))
    assert os.path.exists(p_path("my_frameworks/sframe2/lib/libframework.lib"))
    assert os.path.exists(p_path("my_frameworks/sframe2/foo/bar.txt"))

    # Check files build
    assert os.path.exists(p_path("my_sources/build_stuff.cpp"))
    # note: as the "selective_stuff.cpp" is included in another my_sources dir, is copied twice
    #       it would need manual adjustement of the copy to avoid it
    assert os.path.exists(p_path("my_sources/selective_stuff.cpp"))
    assert os.path.exists(p_path("my_sources/subdir/othersubdir/selective_stuff.cpp"))

    assert os.path.exists(p_path("my_includes/include3.h"))
    assert not os.path.exists(p_path("my_includes/include4.h"))

    assert os.path.exists(p_path("my_libs/blibone.a"))
    assert os.path.exists(p_path("my_libs/blibtwo.a"))

    assert os.path.exists(p_path("my_bins/build_bin.exe"))

    assert os.path.exists(p_path("my_frameworks/sframe1/include/include.h"))
    assert os.path.exists(p_path("my_frameworks/sframe2/include/include.h"))


def test_auto_package_with_components():
    """The files from the components are not mixed in package if they belong to different dirs"""
    client = TestClient()
    conan_file = str(GenConanfile()
                     .with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """

    def source(self):
        tools.save("includes1/component1.hpp", "")
        tools.save("includes2/component2.hpp", "")

    def build(self):
        tools.save("build_libs/component1.a", "")
        tools.save("build_libs/component2.a", "")
        tools.save("build_bins/component3.exe", "")

    def layout(self):
        # Build and source infos
        self.cpp.source.components["component1"].includedirs = ["includes1"]
        self.cpp.source.components["component2"].includedirs = ["includes2"]
        self.cpp.build.components["component1"].libdirs = ["build_libs"]
        self.cpp.build.components["component2"].libdirs = ["build_libs"]
        self.cpp.build.components["component3"].bindirs = ["build_bins"]

        # Package infos
        self.cpp.package.components["component1"].includedirs = ["include"]
        self.cpp.package.components["component2"].includedirs = ["include2"]
        self.cpp.package.components["component1"].libdirs = ["lib"]
        self.cpp.package.components["component2"].libdirs = ["lib"]
        self.cpp.package.components["component3"].bindirs = ["bin"]

    def package(self):
        packager = AutoPackager(self)
        packager.run()
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    package_id = re.search(r"lib/1.0:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, package_id)
    p_folder = client.cache.package_layout(ref).package(pref)

    def p_path(path):
        return os.path.join(p_folder, path)

    # Check directories that shouldn't exist
    assert not os.path.exists(p_path("includes1"))
    assert not os.path.exists(p_path("includes2"))
    assert not os.path.exists(p_path("build_libs"))

    # Check includes
    assert os.path.exists(p_path("include"))
    assert os.path.exists(p_path("include/component1.hpp"))
    assert not os.path.exists(p_path("include/component2.hpp"))
    assert os.path.exists(p_path("include2/component2.hpp"))
    assert not os.path.exists(p_path("include2/component1.hpp"))

    # Check libs
    assert os.path.exists(p_path("lib/component1.a"))
    assert os.path.exists(p_path("lib/component2.a"))

    # Check app
    assert os.path.exists(p_path("bin/component3.exe"))


def test_auto_package_with_components_declared_badly():
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """

    def layout(self):
        # Build and source infos
        self.cpp.source.components["component1"].includedirs = ["includes1"]
        self.cpp.source.components["component2"].includedirs = ["includes2"]
        self.cpp.build.components["component1"].libdirs = ["build_libs"]
        self.cpp.build.components["component2"].libdirs = ["build_libs"]
        self.cpp.build.components["component3"].bindirs = ["build_bins"]

        # Package infos BUT NOT DECLARING component2
        self.cpp.package.components["component1"].includedirs = ["include"]
        self.cpp.package.components["component1"].libdirs = ["lib"]
        self.cpp.package.components["component3"].bindirs = ["bin"]

    def package(self):
        AutoPackager(self).run()
    """

    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@", assert_error=True)
    assert "There are components declared in cpp.source.components or in " \
           "cpp.build.components that are not declared in " \
           "cpp.package.components" in client.out


def test_auto_package_default_patterns():
    """By default:
        self.patterns.source.include = ["*.h", "*.hpp", "*.hxx"]
        self.patterns.build.lib = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.patterns.build.bin = ["*.exe", "*.dll"]
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """
    def source(self):
        tools.save("myincludes/mylib.header","")
        tools.save("myincludes/mylib.h","")
        tools.save("myincludes/mylib.hpp","")
        tools.save("myincludes/mylib.hxx","")

    def build(self):
        tools.save("ugly_build/mylib.a", "")
        tools.save("ugly_build/mylib.so", "")
        tools.save("ugly_build/mylib.so.0", "")
        tools.save("ugly_build/mylib.lib", "")
        tools.save("ugly_build/mylib.dylib", "")
        tools.save("ugly_build/app.exe", "")
        tools.save("ugly_build/app.dll", "")
        tools.save("ugly_build/mylib.janderclander", "")

    def layout(self):
        self.cpp.source.includedirs = ["myincludes"]
        self.cpp.build.libdirs = ["ugly_build"]
        self.cpp.build.bindirs = ["ugly_build"]

    def package(self):
        AutoPackager(self).run()
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    package_id = re.search(r"lib/1.0:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, package_id)
    p_folder = client.cache.package_layout(ref).package(pref)

    assert set(os.listdir(os.path.join(p_folder, "lib"))) == {"mylib.a", "mylib.so", "mylib.so.0",
                                                              "mylib.dylib", "mylib.lib"}
    assert set(os.listdir(os.path.join(p_folder, "include"))) == {"mylib.h", "mylib.hpp",
                                                                  "mylib.hxx"}
    assert set(os.listdir(os.path.join(p_folder, "bin"))) == {"app.exe", "app.dll"}


def test_auto_package_default_folders_with_components():
    """By default, the cpp_info of the components are empty"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """
    def layout(self):
        for el in [self.cpp.source, self.cpp.build]:
            # The defaults for cpp.build and cpp.source are empty
            assert el.components["foo"].includedirs is None
            assert el.components["foo"].libdirs is None
            assert el.components["foo"].bindirs is None
            assert el.components["foo"].frameworkdirs is None
            assert el.components["foo"].srcdirs is None
            assert el.components["foo"].resdirs is None

        # The defaults for cpp.package are filled includedirs and libdirs and bindirs
        assert self.cpp.package.components["foo"].includedirs is not None
        assert self.cpp.package.components["foo"].libdirs is not None
        assert self.cpp.package.components["foo"].bindirs is not None
        assert self.cpp.package.components["foo"].frameworkdirs is None
        assert self.cpp.package.components["foo"].srcdirs is None
        assert self.cpp.package.components["foo"].resdirs is None

    def package(self):
        AutoPackager(self).run()
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")


def test_auto_package_with_custom_package_too():
    """We can also declare the package() method and call explicitly to the
       self.folders.package_files()"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """
    def source(self):
        tools.save("myincludes/mylib.header","")

    def build(self):
        tools.save("ugly_build/mylib.a", "")

    def layout(self):
        self.cpp.source.includedirs = ["myincludes"]
        self.cpp.build.libdirs = ["ugly_build"]

    def package(self):
        packager = AutoPackager(self)
        packager.patterns.source.include = ["*.header"]
        packager.patterns.build.lib = ["*.a"]
        packager.run()
        assert os.path.exists(os.path.join(self.package_folder, "include", "mylib.header"))
        assert os.path.exists(os.path.join(self.package_folder, "lib", "mylib.a"))
        self.output.warn("Package method called!")

    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    assert "Package method called!" in client.out


def test_auto_package_only_one_destination():
    """If the layout declares more than one destination folder it fails, because it cannot guess
    where to put the artifacts (very weird situation a package with two include/)"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conans import tools")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """
    def source(self):
        tools.save("myincludes/mylib.header","")

    def build(self):
       tools.save("ugly_build/mylib.a", "")

    def layout(self):
       self.cpp.source.includedirs = ["myincludes"]
       self.cpp.build.libdirs = ["ugly_build"]
       self.cpp.build.bindirs = ["ugly_build"]
       self.cpp.build.frameworkdirs = ["ugly_build"]
       self.cpp.build.srcdirs = ["ugly_build"]
       self.cpp.build.builddirs = ["ugly_build"]
       self.cpp.build.resdirs = ["ugly_build"]

       self.cpp.package.{} = ["folder1", "folder2"]

    def package(self):
        packager = AutoPackager(self)
        packager.patterns.source.include = ["*.header"]
        packager.patterns.build.lib = ["*.a"]
        packager.run()

    """
    for dirs in ["includedirs", "builddirs", "bindirs", "srcdirs", "frameworkdirs", "libdirs",
                 "resdirs"]:
        client.save({"conanfile.py": conan_file.format(dirs)})
        client.run("create . lib/1.0@", assert_error=True)
        assert "The package has more than 1 cpp_info.{}, " \
               "cannot package automatically".format(dirs) in client.out
