import textwrap

import pytest
import six

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_cpp_info_editable():

    client = TestClient()

    conan_hello = str(GenConanfile())
    conan_hello += """
    def layout(self):
        self.folders.source = "my_sources"
        self.folders.build = "my_build"

        self.cpp.build.includedirs = ["my_include"]
        self.cpp.build.libdirs = ["my_libdir"]
        self.cpp.build.libs = ["hello"]
        self.cpp.build.objects = ["myobjs/myobject.o"]
        self.cpp.build.frameworkdirs = []  # Empty list is also explicit priority declaration

        self.cpp.source.cxxflags = ["my_cxx_flag"]
        self.cpp.source.includedirs = ["my_include_source"]
        self.cpp.source.builddirs = ["my_builddir_source"]
        self.cpp.source.set_property("cmake_build_modules", ["mypath/mybuildmodule"])

        self.cpp.package.libs = ["lib_when_package"]

    def package_info(self):
        # when editable: This one will be discarded because declared in build
        self.cpp_info.includedirs = ["package_include"]

        # when editable: This one will be discarded because declared in build
        self.cpp_info.libs.append("lib_when_package2")

        self.cpp_info.objects = ["myobject.o"]
        self.cpp_info.set_property("cmake_build_modules", ["mymodules/mybuildmodule"])

        # when editable: This one will be discarded because declared in source
        self.cpp_info.cxxflags.append("my_cxx_flag2")

        # when editable: This one will be discarded because declared in source
        self.cpp_info.frameworkdirs.append("package_frameworks_path")

        # when editable: This one WONT be discarded as has not been declared in the editables layout
        self.cpp_info.cflags.append("my_c_flag")
     """

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@")
    ref = ConanFileReference.loads("hello/1.0")
    pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
    package_folder = client.cache.package_layout(pref.ref).package(pref).replace("\\", "/") + "/"

    conan_consumer = textwrap.dedent("""
    import os

    from conans import ConanFile, tools

    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        requires = "hello/1.0"
        def build(self):
            info = self.dependencies["hello"].cpp_info
            self.output.warn("**includedirs:{}**".format(info.includedirs))
            self.output.warn("**libdirs:{}**".format(info.libdirs))
            self.output.warn("**builddirs:{}**".format(info.builddirs))
            self.output.warn("**frameworkdirs:{}**".format(info.frameworkdirs))
            self.output.warn("**libs:{}**".format(info.libs))
            self.output.warn("**objects:{}**".format(info.objects))
            self.output.warn("**build_modules:{}**".format(info.get_property("cmake_build_modules")))
            self.output.warn("**cxxflags:{}**".format(info.cxxflags))
            self.output.warn("**cflags:{}**".format(info.cflags))
    """)
    # When hello is not editable
    client2 = TestClient(client.cache_folder)
    client2.save({"conanfile.py": conan_consumer})
    client2.run("create . lib/1.0@")
    out = str(client2.out).replace(r"\\", "/").replace(package_folder, "")
    assert "**includedirs:['package_include']**" in out
    assert "**libdirs:['lib']**" in out
    assert "**builddirs:['']**" in out
    assert "**frameworkdirs:['package_frameworks_path']**" in out
    assert "**libs:['lib_when_package', 'lib_when_package2']**" in out
    assert "**objects:['myobject.o']**" in out
    assert "**build_modules:['mymodules/mybuildmodule']**" in out
    assert "**cxxflags:['my_cxx_flag2']**" in out
    assert "**cflags:['my_c_flag']**" in out

    # When hello is editable
    client.save({"conanfile.py": conan_hello})
    client.run("editable add . hello/1.0@")

    # Create the consumer again, now it will use the hello editable
    client2.run("create . lib/1.0@")
    base_folder = client.current_folder.replace("\\", "/") + "/"
    out = str(client2.out).replace(r"\\", "/").replace(base_folder, "")
    assert "**includedirs:['my_sources/my_include_source', 'my_build/my_include']**" in out
    assert "**libdirs:['my_build/my_libdir']**" in out
    assert "**builddirs:['my_sources/my_builddir_source']**" in out
    assert "**libs:['hello']**" in out
    assert "**objects:['my_build/myobjs/myobject.o']**" in out
    assert "**build_modules:['my_sources/mypath/mybuildmodule']**" in out
    assert "**cxxflags:['my_cxx_flag']**" in out
    assert "**cflags:['my_c_flag']**" in out
    assert "**frameworkdirs:[]**" in out


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_cpp_info_components_editable():

    client = TestClient()

    conan_hello = str(GenConanfile())
    conan_hello += """
    def layout(self):
        self.folders.source = "my_sources"
        self.folders.build = "my_build"

        self.cpp.build.components["foo"].includedirs = ["my_include_foo"]
        self.cpp.build.components["foo"].libdirs = ["my_libdir_foo"]
        self.cpp.build.components["foo"].libs = ["hello_foo"]
        self.cpp.build.components["foo"].objects = ["myobjs/myobject.o"]

        self.cpp.build.components["var"].includedirs = ["my_include_var"]
        self.cpp.build.components["var"].libdirs = ["my_libdir_var"]
        self.cpp.build.components["var"].libs = ["hello_var"]

        self.cpp.source.components["foo"].cxxflags = ["my_cxx_flag_foo"]
        self.cpp.source.components["foo"].includedirs = ["my_include_source_foo"]
        self.cpp.source.components["foo"].builddirs = ["my_builddir_source_foo"]
        self.cpp.source.components["foo"].set_property("cmake_build_modules",
                                                      ["mypath/mybuildmodule"])
        self.cpp.source.components["var"].cxxflags = ["my_cxx_flag_var"]
        self.cpp.source.components["var"].includedirs = ["my_include_source_var"]
        self.cpp.source.components["var"].builddirs = ["my_builddir_source_var"]

        self.cpp.package.components["foo"].libs = ["lib_when_package_foo"]
        self.cpp.package.components["var"].libs = ["lib_when_package_var"]

    def package_info(self):
        # when editable: This one will be discarded because declared in build
        self.cpp_info.components["foo"].includedirs = ["package_include_foo"]

        # when editable: This one will be discarded because declared in build
        self.cpp_info.components["foo"].libs.append("lib_when_package2_foo")

        self.cpp_info.components["foo"].objects = ["myobject.o"]
        self.cpp_info.components["foo"].set_property("cmake_build_modules",
                                                    ["mymodules/mybuildmodule"])

        # when editable: This one will be discarded because declared in source
        self.cpp_info.components["foo"].cxxflags.append("my_cxx_flag2_foo")

        # when editable: This one WONT be discarded as has not been declared in the editables layout
        self.cpp_info.components["foo"].cflags.append("my_c_flag_foo")

        # when editable: This one will be discarded because declared in build
        self.cpp_info.components["var"].includedirs = ["package_include_var"]

        # when editable: This one will be discarded because declared in build
        self.cpp_info.components["var"].libs.append("lib_when_package2_var")

        # when editable: This one will be discarded because declared in source
        self.cpp_info.components["var"].cxxflags.append("my_cxx_flag2_var")

        # when editable: This one WONT be discarded as has not been declared in the editables layout
        self.cpp_info.components["var"].cflags.append("my_c_flag_var")
     """

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@")
    ref = ConanFileReference.loads("hello/1.0")
    pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
    package_folder = client.cache.package_layout(pref.ref).package(pref).replace("\\", "/") + "/"

    conan_consumer = textwrap.dedent("""
    import os

    from conans import ConanFile, tools

    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        requires = "hello/1.0"
        def build(self):
            info = self.dependencies["hello"].cpp_info
            self.output.warn("**FOO includedirs:{}**".format(info.components["foo"].includedirs))
            self.output.warn("**FOO libdirs:{}**".format(info.components["foo"].libdirs))
            self.output.warn("**FOO builddirs:{}**".format(info.components["foo"].builddirs))
            self.output.warn("**FOO libs:{}**".format(info.components["foo"].libs))
            self.output.warn("**FOO cxxflags:{}**".format(info.components["foo"].cxxflags))
            self.output.warn("**FOO cflags:{}**".format(info.components["foo"].cflags))
            self.output.warn("**FOO objects:{}**".format(info.components["foo"].objects))
            self.output.warn("**FOO build_modules:{}**".format(
                                        info.components["foo"].get_property("cmake_build_modules")))

            self.output.warn("**VAR includedirs:{}**".format(info.components["var"].includedirs))
            self.output.warn("**VAR libdirs:{}**".format(info.components["var"].libdirs))
            self.output.warn("**VAR builddirs:{}**".format(info.components["var"].builddirs))
            self.output.warn("**VAR libs:{}**".format(info.components["var"].libs))
            self.output.warn("**VAR cxxflags:{}**".format(info.components["var"].cxxflags))
            self.output.warn("**VAR cflags:{}**".format(info.components["var"].cflags))
    """)
    # When hello is not editable
    client2 = TestClient(client.cache_folder)
    client2.save({"conanfile.py": conan_consumer})
    client2.run("create . lib/1.0@")
    out = str(client2.out).replace(r"\\", "/").replace(package_folder, "")
    assert "**FOO includedirs:['package_include_foo']**" in out
    assert "**FOO libdirs:['lib']**" in out  # The components does have default dirs
    assert "**FOO builddirs:[]**" in out  # The components don't have default dirs for builddirs
    assert "**FOO libs:['lib_when_package_foo', 'lib_when_package2_foo']**" in out
    assert "**FOO objects:['myobject.o']**" in out
    assert "**FOO build_modules:['mymodules/mybuildmodule']**" in out
    assert "**FOO cxxflags:['my_cxx_flag2_foo']**" in out
    assert "**FOO cflags:['my_c_flag_foo']**" in out

    assert "**VAR includedirs:['package_include_var']**" in out
    assert "**VAR libdirs:['lib']**" in out  # The components does have default dirs
    assert "**VAR builddirs:[]**" in out  # The components don't have default dirs
    assert "**VAR libs:['lib_when_package_var', 'lib_when_package2_var']**" in out
    assert "**VAR cxxflags:['my_cxx_flag2_var']**" in out
    assert "**VAR cflags:['my_c_flag_var']**" in out

    # When hello is editable
    client.save({"conanfile.py": conan_hello})
    client.run("editable add . hello/1.0@")

    # Create the consumer again, now it will use the hello editable
    client2.run("create . lib/1.0@")
    base_folder = client.current_folder.replace("\\", "/") + "/"
    out = str(client2.out).replace(r"\\", "/").replace(base_folder, "")
    assert "**FOO includedirs:['my_sources/my_include_source_foo', " \
           "'my_build/my_include_foo']**" in out
    assert "**FOO libdirs:['my_build/my_libdir_foo']**" in out
    assert "**FOO builddirs:['my_sources/my_builddir_source_foo']**" in out
    assert "**FOO libs:['hello_foo']**" in out
    assert "**FOO objects:['my_build/myobjs/myobject.o']**" in out
    assert "**FOO build_modules:['my_sources/mypath/mybuildmodule']**" in out
    assert "**FOO cxxflags:['my_cxx_flag_foo']**" in out
    assert "**FOO cflags:['my_c_flag_foo']**" in out

    assert "**VAR includedirs:['my_sources/my_include_source_var', " \
           "'my_build/my_include_var']**" in out
    assert "**VAR libdirs:['my_build/my_libdir_var']**" in out
    assert "**VAR builddirs:['my_sources/my_builddir_source_var']**" in out
    assert "**VAR libs:['hello_var']**" in out
    assert "**VAR cxxflags:['my_cxx_flag_var']**" in out
    assert "**VAR cflags:['my_c_flag_var']**" in out
