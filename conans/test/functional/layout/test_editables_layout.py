import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cpp_info_editable():

    client = TestClient()

    conan_hello = str(GenConanfile())
    conan_hello += """
    def layout(self):
        self.folders.source = "my_sources"
        self.folders.build = "my_build"

        self.infos.build.includedirs = ["my_include"]
        self.infos.build.libdirs = ["my_libdir"]
        self.infos.build.libs = ["hello"]

        self.infos.source.cxxflags = ["my_cxx_flag"]
        self.infos.source.includedirs = ["my_include_source"]
        self.infos.source.builddirs = ["my_builddir_source"]

        self.infos.package.libs = ["lib_when_package"]

    def package_info(self):
        # when editable: This one will be discarded because declared in build
        self.cpp_info.includedirs = ["package_include"]

        # when editable: This one will be discarded because declared in build
        self.cpp_info.libs.append("lib_when_package2")

        # when editable: This one will be discarded because declared in source
        self.cpp_info.cxxflags.append("my_cxx_flag2")

        # when editable: This one WONT be discarded as has not been declared in the editables layout
        self.cpp_info.cflags.append("my_c_flag")
     """

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@")

    conan_consumer = textwrap.dedent("""
    import os

    from conans import ConanFile, tools

    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        requires = "hello/1.0"
        def build(self):
            info = self.dependencies.requires["hello"].cpp_info
            self.output.warn("**includedirs:{}**".format(info.includedirs))
            self.output.warn("**libdirs:{}**".format(info.libdirs))
            self.output.warn("**builddirs:{}**".format(info.builddirs))
            self.output.warn("**libs:{}**".format(info.libs))
            self.output.warn("**cxxflags:{}**".format(info.cxxflags))
            self.output.warn("**cflags:{}**".format(info.cflags))
    """)
    # When hello is not editable
    client2 = TestClient(client.cache_folder)
    client2.save({"conanfile.py": conan_consumer})
    client2.run("create . lib/1.0@")
    assert "**includedirs:['package_include']**" in client2.out
    assert "**libdirs:['lib']**" in client2.out
    assert "**builddirs:['']**" in client2.out
    assert "**libs:['lib_when_package', 'lib_when_package2']**" in client2.out
    assert "**cxxflags:['my_cxx_flag2']**" in client2.out
    assert "**cflags:['my_c_flag']**" in client2.out

    # When hello is editable
    client.save({"conanfile.py": conan_hello})
    client.run("editable add . hello/1.0@")

    # Create the consumer again, now it will use the hello editable
    client2.run("create . lib/1.0@")
    assert "**includedirs:['my_sources/my_include_source', 'my_build/my_include']**" in client2.out
    assert "**libdirs:['my_build/my_libdir']**" in client2.out
    assert "**builddirs:['my_sources/my_builddir_source']**" in client2.out
    assert "**libs:['hello']**" in client2.out
    assert "**cxxflags:['my_cxx_flag']**" in client2.out
    assert "**cflags:['my_c_flag']**" in client2.out
