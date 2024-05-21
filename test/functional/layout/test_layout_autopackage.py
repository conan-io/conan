import os

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def get_latest_package_reference(cache, ref, pkgid):
    latest_rrev = cache.get_latest_recipe_reference(ref)
    pref = PkgReference(latest_rrev, pkgid)
    prefs = cache.get_package_revisions_references(pref, only_latest_prev=True)
    return prefs[0]


def test_auto_package_no_components():
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("from conan.tools.files import AutoPackager, save"))
    conan_file += """

    def source(self):
        save(self, "source_sources/source_stuff.cpp", "")
        save(self, "source_includes/include1.hpp", "")
        save(self, "source_includes/include2.hpp", "")
        save(self, "source_includes2/include3.h", "")
        save(self, "source_libs/slibone.a", "")
        save(self, "source_libs/slibtwo.a", "")
        save(self, "source_libs/bin_to_discard.exe", "")
        save(self, "source_bins/source_bin.exe", "")
        save(self, "source_frameworks/sframe1/include/include.h", "")
        save(self, "source_frameworks/sframe2/include/include.h", "")
        save(self, "source_frameworks/sframe1/lib/libframework.lib", "")
        save(self, "source_frameworks/sframe2/lib/libframework.lib", "")
        save(self, "source_frameworks/sframe2/foo/bar.txt", "")

    def build(self):
        save(self, "build_sources/build_stuff.cpp", "")
        save(self, "build_sources/subdir/othersubdir/selective_stuff.cpp", "")
        save(self, "build_includes/include3.h", "")
        save(self, "build_includes/include4.hpp", "")
        save(self, "build_libs/blibone.a", "")
        save(self, "build_libs/blibtwo.a", "")
        save(self, "build_bins/build_bin.exe", "")
        save(self, "build_frameworks/bframe1/include/include.h", "")
        save(self, "build_frameworks/bframe2/include/include.h", "")

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
    client.run("create . --name=lib --version=1.0")
    assert "AutoPackager is **** deprecated ****" in client.out
    package_id = client.created_package_id("lib/1.0")

    ref = RecipeReference.loads("lib/1.0@")
    prev = get_latest_package_reference(client.cache, ref, package_id)

    p_folder = client.cache.pkg_layout(prev).package()

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
                     .with_import("from conan.tools.files import AutoPackager, save"))
    conan_file += """

    def source(self):
        save(self, "includes1/component1.hpp", "")
        save(self, "includes2/component2.hpp", "")

    def build(self):
        save(self, "build_libs/component1.a", "")
        save(self, "build_libs/component2.a", "")
        save(self, "build_bins/component3.exe", "")

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
    client.run("create . --name=lib --version=1.0")
    package_id = client.created_package_id("lib/1.0")

    ref = RecipeReference.loads("lib/1.0@")
    pref = get_latest_package_reference(client.cache, ref, package_id)
    p_folder = client.cache.pkg_layout(pref).package()

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
    client.run("create . --name=lib --version=1.0", assert_error=True)
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
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager, save"))
    conan_file += """
    def source(self):
        save(self, "myincludes/mylib.header","")
        save(self, "myincludes/mylib.h","")
        save(self, "myincludes/mylib.hpp","")
        save(self, "myincludes/mylib.hxx","")

    def build(self):
        save(self, "ugly_build/mylib.a", "")
        save(self, "ugly_build/mylib.so", "")
        save(self, "ugly_build/mylib.so.0", "")
        save(self, "ugly_build/mylib.lib", "")
        save(self, "ugly_build/mylib.dylib", "")
        save(self, "ugly_build/app.exe", "")
        save(self, "ugly_build/app.dll", "")
        save(self, "ugly_build/mylib.janderclander", "")

    def layout(self):
        self.cpp.source.includedirs = ["myincludes"]
        self.cpp.build.libdirs = ["ugly_build"]
        self.cpp.build.bindirs = ["ugly_build"]

    def package(self):
        AutoPackager(self).run()
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . --name=lib --version=1.0")
    package_id = client.created_package_id("lib/1.0")
    ref = RecipeReference.loads("lib/1.0@")
    pref = get_latest_package_reference(client.cache, ref, package_id)
    p_folder = client.cache.pkg_layout(pref).package()

    assert set(os.listdir(os.path.join(p_folder, "lib"))) == {"mylib.a", "mylib.so", "mylib.so.0",
                                                              "mylib.dylib", "mylib.lib"}
    assert set(os.listdir(os.path.join(p_folder, "include"))) == {"mylib.h", "mylib.hpp",
                                                                  "mylib.hxx"}
    assert set(os.listdir(os.path.join(p_folder, "bin"))) == {"app.exe", "app.dll"}


def test_auto_package_default_folders_with_components():
    """By default, the cpp_info of the components are empty"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager"))
    conan_file += """
    def layout(self):
        for el in [self.cpp.source, self.cpp.build]:
            assert el.components["foo"].includedirs == []
            assert el.components["foo"].libdirs == []
            assert el.components["foo"].bindirs == []
            assert el.components["foo"].frameworkdirs == []
            assert el.components["foo"].srcdirs == []
            assert el.components["foo"].resdirs == []

        assert self.cpp.package.components["foo"].includedirs == ["include"]
        assert self.cpp.package.components["foo"].libdirs == ["lib"]
        assert self.cpp.package.components["foo"].bindirs == ["bin"]
        assert self.cpp.package.components["foo"].frameworkdirs == []
        assert self.cpp.package.components["foo"].srcdirs == []
        assert self.cpp.package.components["foo"].resdirs == []

    def package(self):
        AutoPackager(self).run()
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . --name=lib --version=1.0")


def test_auto_package_with_custom_package_too():
    """We can also declare the package() method and call explicitly to the
       self.folders.package_files()"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager, save"))
    conan_file += """
    def source(self):
        save(self, "myincludes/mylib.header","")

    def build(self):
        save(self, "ugly_build/mylib.a", "")

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
        self.output.warning("Package method called!")

    """
    client.save({"conanfile.py": conan_file})
    client.run("create . --name=lib --version=1.0")
    assert "Package method called!" in client.out


def test_auto_package_only_one_destination():
    """If the layout declares more than one destination folder it fails, because it cannot guess
    where to put the artifacts (very weird situation a package with two include/)"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type")
                     .with_import("import os")
                     .with_import("from conan.tools.files import AutoPackager, save"))
    conan_file += """
    def source(self):
        save(self, "myincludes/mylib.header","")

    def build(self):
       save(self, "ugly_build/mylib.a", "")

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
        client.run("create . --name=lib --version=1.0", assert_error=True)
        assert "The package has more than 1 cpp_info.{}, " \
               "cannot package automatically".format(dirs) in client.out
