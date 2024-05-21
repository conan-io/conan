import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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
    client.run("create . --name=hello --version=1.0")
    package_folder = client.created_layout().package().replace("\\", "/") + "/"

    conan_consumer = textwrap.dedent("""
    import os

    from conan import ConanFile, tools

    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        requires = "hello/1.0"
        def build(self):
            info = self.dependencies["hello"].cpp_info

            self.output.warning("**includedirs:{}**".format(info.includedirs))
            self.output.warning("**libdirs:{}**".format(info.libdirs))
            self.output.warning("**builddirs:{}**".format(info.builddirs))
            self.output.warning("**frameworkdirs:{}**".format(info.frameworkdirs))
            self.output.warning("**libs:{}**".format(info.libs))
            self.output.warning("**objects:{}**".format(info.objects))
            self.output.warning("**build_modules:{}**".format(info.get_property("cmake_build_modules")))
            self.output.warning("**cxxflags:{}**".format(info.cxxflags))
            self.output.warning("**cflags:{}**".format(info.cflags))
    """)
    # When hello is not editable
    client2 = TestClient(client.cache_folder)
    client2.save({"conanfile.py": conan_consumer})
    client2.run("create . --name=lib --version=1.0")
    out = str(client2.out).replace(r"\\", "/").replace(package_folder, "")
    assert "**includedirs:['package_include']**" in out
    assert "**libdirs:['lib']**" in out
    assert "**builddirs:[]**" in out
    assert "**frameworkdirs:['package_frameworks_path']**" in out
    assert "**libs:['lib_when_package', 'lib_when_package2']**" in out
    assert "**objects:['myobject.o']**" in out
    assert "**build_modules:['mymodules/mybuildmodule']**" in out
    assert "**cxxflags:['my_cxx_flag2']**" in out
    assert "**cflags:['my_c_flag']**" in out

    # When hello is editable
    client.save({"conanfile.py": conan_hello})
    client.run("editable add . --name=hello --version=1.0")

    # Create the consumer again, now it will use the hello editable
    client2.run("create . --name=lib --version=1.0")
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
    client.run("create . --name=hello --version=1.0")
    package_folder = client.created_layout().package().replace("\\", "/") + "/"

    conan_consumer = textwrap.dedent("""
    import os

    from conan import ConanFile, tools

    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        requires = "hello/1.0"
        def build(self):
            info = self.dependencies["hello"].cpp_info

            self.output.warning("**FOO includedirs:{}**".format(info.components["foo"].includedirs))
            self.output.warning("**FOO libdirs:{}**".format(info.components["foo"].libdirs))
            self.output.warning("**FOO builddirs:{}**".format(info.components["foo"].builddirs))
            self.output.warning("**FOO libs:{}**".format(info.components["foo"].libs))
            self.output.warning("**FOO cxxflags:{}**".format(info.components["foo"].cxxflags))
            self.output.warning("**FOO cflags:{}**".format(info.components["foo"].cflags))
            self.output.warning("**FOO objects:{}**".format(info.components["foo"].objects))
            self.output.warning("**FOO build_modules:{}**".format(
                                        info.components["foo"].get_property("cmake_build_modules")))

            self.output.warning("**VAR includedirs:{}**".format(info.components["var"].includedirs))
            self.output.warning("**VAR libdirs:{}**".format(info.components["var"].libdirs))
            self.output.warning("**VAR builddirs:{}**".format(info.components["var"].builddirs))
            self.output.warning("**VAR libs:{}**".format(info.components["var"].libs))
            self.output.warning("**VAR cxxflags:{}**".format(info.components["var"].cxxflags))
            self.output.warning("**VAR cflags:{}**".format(info.components["var"].cflags))
    """)
    # When hello is not editable
    client2 = TestClient(client.cache_folder)
    client2.save({"conanfile.py": conan_consumer})
    client2.run("create . --name=lib --version=1.0")

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
    client.run("editable add . --name=hello --version=1.0")

    # Create the consumer again, now it will use the hello editable
    client2.run("create . --name=lib --version=1.0")
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


def test_editable_package_folder():
    """ This test checks the behavior that self.package_folder is NOT defined (i.e = None)
    for editable packages, so it cannot be used in ``package_info()`` method
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "arch", "build_type"

            def package_info(self):
                self.output.info("PKG FOLDER={}!!!".format(self.package_folder))

            def layout(self):
                cmake_layout(self)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    c.run("editable add .")
    c.run("install --requires=pkg/0.1@")
    assert "pkg/0.1: PKG FOLDER=None!!!"


def test_editable_components_absolute_paths():
    """
    this was failing in https://github.com/conan-io/conan/issues/14777
    because components aggregation had a bug
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "alpha"
            version = "1.0"

            def layout(self):
                self.cpp.source.components["headers"].includedirs = ["include222"]
                self.cpp.build.components["alpha1"].libdirs = ["alpha1",]
                self.cpp.build.components["alpha2"].libdirs = ["alpha2"]
                self.cpp.build.components["alpha_exe"].bindirs = ["alpha_exe"]
        """)
    test = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
            """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": test})
    c.run("editable add .")
    c.run("create .")
    # This used to crash due to "include" is not absolute path, now it works
    assert "Testing the package" in c.out
