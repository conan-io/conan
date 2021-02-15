import os

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_auto_package_no_components():
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools"))
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


    def shape(self):
        self.layout.source.folder = "my_source"
        self.layout.build.folder = "my_build"
        self.layout.generators.folder = "my_build/generators"

        # Package locations
        self.layout.package.cpp_info.includedirs = ["my_includes"]
        self.layout.package.cpp_info.srcdirs = ["my_sources"]
        self.layout.package.cpp_info.bindirs = ["my_bins"]
        self.layout.package.cpp_info.libdirs = ["my_libs"]
        self.layout.package.cpp_info.frameworkdirs = ["my_frameworks"]

        # Source CPP INFO
        self.layout.source.cpp_info.srcdirs = ["source_sources"]
        self.layout.source.cpp_info.includedirs = ["source_includes", "source_includes2"]
        self.layout.source.cpp_info.libdirs = ["source_libs"]
        self.layout.source.cpp_info.bindirs = ["source_bins"]
        self.layout.source.cpp_info.frameworkdirs = ["source_frameworks"]

        # Source File patterns
        self.layout.source.include_patterns = ["*.hpp"] # Discard include3.h from source
        self.layout.source.lib_patterns = ["*.a"]
        self.layout.source.bin_patterns = ["*.exe"]
        self.layout.source.src_patterns = ["*.cpp"]
        self.layout.source.framework_patterns = ["sframe*"]

        # Build CPP INFO
        self.layout.build.cpp_info.srcdirs = ["build_sources",
                                              "build_sources/subdir/othersubdir"]
        self.layout.build.cpp_info.includedirs = ["build_includes"]
        self.layout.build.cpp_info.libdirs = ["build_libs"]
        self.layout.build.cpp_info.bindirs = ["build_bins"]
        self.layout.build.cpp_info.frameworkdirs = ["build_frameworks"]

        # Build File patterns
        self.layout.build.include_patterns = ["*.h"]
        self.layout.build.lib_patterns = ["*.a"]
        self.layout.build.bin_patterns = ["*.exe"]
        self.layout.build.src_patterns = ["*.cpp"]
        self.layout.build.framework_patterns = ["bframe*"]

    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "4024617540c4f240a6a5e8911b0de9ef38a11a72")
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
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools"))
    conan_file += """

    def source(self):
        tools.save("includes1/component1.hpp", "")
        tools.save("includes2/component2.hpp", "")

    def build(self):
        tools.save("build_libs/component1.a", "")
        tools.save("build_libs/component2.a", "")
        tools.save("build_bins/component3.exe", "")

    def shape(self):
        # Build and source infos
        self.layout.source.cpp_info.components["component1"].includedirs = ["includes1"]
        self.layout.source.cpp_info.components["component2"].includedirs = ["includes2"]
        self.layout.build.cpp_info.components["component1"].libdirs = ["build_libs"]
        self.layout.build.cpp_info.components["component2"].libdirs = ["build_libs"]
        self.layout.build.cpp_info.components["component3"].bindirs = ["build_bins"]

        # Package infos
        self.layout.package.cpp_info.components["component1"].includedirs = ["include"]
        self.layout.package.cpp_info.components["component2"].includedirs = ["include2"]
        self.layout.package.cpp_info.components["component1"].libdirs = ["lib"]
        self.layout.package.cpp_info.components["component2"].libdirs = ["lib"]
        self.layout.package.cpp_info.components["component3"].bindirs = ["bin"]

    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "4024617540c4f240a6a5e8911b0de9ef38a11a72")
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
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools"))
    conan_file += """

    def shape(self):
        # Build and source infos
        self.layout.source.cpp_info.components["component1"].includedirs = ["includes1"]
        self.layout.source.cpp_info.components["component2"].includedirs = ["includes2"]
        self.layout.build.cpp_info.components["component1"].libdirs = ["build_libs"]
        self.layout.build.cpp_info.components["component2"].libdirs = ["build_libs"]
        self.layout.build.cpp_info.components["component3"].bindirs = ["build_bins"]

        # Package infos BUT NOT DECLARING component2
        self.layout.package.cpp_info.components["component1"].includedirs = ["include"]
        self.layout.package.cpp_info.components["component1"].libdirs = ["lib"]
        self.layout.package.cpp_info.components["component3"].bindirs = ["bin"]
    """

    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@", assert_error=True)
    assert "There are components declared in layout.source.cpp_info.components or in layout." \
           "build.cpp_info.components that are not declared in layout.package.cpp_info." \
           "components" in client.out


def test_auto_package_default_patterns():
    """By default:
        self.source.include_patterns = ["*.h", "*.hpp", "*.hxx"]
        self.build.lib_patterns = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.build.bin_patterns = ["*.exe", "*.dll"]
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools").with_import("import os"))
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

    def shape(self):
        self.layout.source.cpp_info.includedirs = ["myincludes"]
        self.layout.build.cpp_info.libdirs = ["ugly_build"]
        self.layout.build.cpp_info.bindirs = ["ugly_build"]
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "4024617540c4f240a6a5e8911b0de9ef38a11a72")
    p_folder = client.cache.package_layout(ref).package(pref)

    assert set(os.listdir(os.path.join(p_folder, "lib"))) == {"mylib.a", "mylib.so", "mylib.so.0",
                                                              "mylib.dylib", "mylib.lib"}
    assert set(os.listdir(os.path.join(p_folder, "include"))) == {"mylib.h", "mylib.hpp",
                                                                  "mylib.hxx"}
    assert set(os.listdir(os.path.join(p_folder, "bin"))) == {"app.exe", "app.dll"}


def test_auto_package_default_patterns_with_components():
    """By default, the cpp_info of the components of source and build are empty, and the package
     by default keep the values"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools").with_import("import os"))
    conan_file += """
    def shape(self):
        for el in [self.layout.source, self.layout.build]:
            assert el.cpp_info.components["foo"].includedirs == []
            assert el.cpp_info.components["foo"].libdirs == []
            assert el.cpp_info.components["foo"].bindirs == []
            assert el.cpp_info.components["foo"].frameworkdirs == []
            assert el.cpp_info.components["foo"].srcdirs == []
            assert el.cpp_info.components["foo"].resdirs == []

        assert self.layout.package.cpp_info.components["foo"].includedirs == ["include"]
        assert self.layout.package.cpp_info.components["foo"].libdirs == ["lib"]
        assert self.layout.package.cpp_info.components["foo"].bindirs == ["bin"]
        assert self.layout.package.cpp_info.components["foo"].frameworkdirs == ["Frameworks"]
        assert self.layout.package.cpp_info.components["foo"].srcdirs == []
        assert self.layout.package.cpp_info.components["foo"].resdirs == ["res"]
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")


def test_auto_package_with_custom_package_too():
    """We can also declare the package() method and call explicitly to the
       self.layout.package_files()"""
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools").with_import("import os"))
    conan_file += """
    def source(self):
        tools.save("myincludes/mylib.header","")

    def build(self):
        tools.save("ugly_build/mylib.a", "")

    def shape(self):
        self.layout.source.cpp_info.includedirs = ["myincludes"]
        self.layout.build.cpp_info.libdirs = ["ugly_build"]
        self.layout.source.include_patterns = ["*.header"]
        self.layout.build.lib_patterns = ["*.a"]

    def package(self):
        self.layout.package_files()
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
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conans import tools").with_import("import os"))
    conan_file += """
    def source(self):
        tools.save("myincludes/mylib.header","")

    def build(self):
       tools.save("ugly_build/mylib.a", "")

    def shape(self):
       self.layout.source.cpp_info.includedirs = ["myincludes"]
       self.layout.build.cpp_info.libdirs = ["ugly_build"]
       self.layout.source.include_patterns = ["*.header"]
       self.layout.build.lib_patterns = ["*.a"]

       self.layout.package.cpp_info.{} = ["folder1", "folder2"]

    """
    for dirs in ["includedirs", "builddirs", "bindirs", "srcdirs", "frameworkdirs", "libdirs",
                 "resdirs"]:
        client.save({"conanfile.py": conan_file.format(dirs)})
        client.run("create . lib/1.0@", assert_error=True)
        assert "The package has more than 1 cpp_info.{}, " \
               "cannot package automatically".format(dirs) in client.out
