import re
import textwrap

from conan.test.utils.tools import TestClient


def test_sconsdeps():
    dep = textwrap.dedent("""
        from conan import ConanFile
        class ExampleConanIntegration(ConanFile):
            name = "{dep}"
            version = "0.1"
            def package_info(self):
                self.cpp_info.includedirs = ["{dep}_includedir"]
                self.cpp_info.libdirs = ["{dep}_libdir"]
                self.cpp_info.bindirs = ["{dep}_bindir"]
                self.cpp_info.libs = ["{dep}_lib"]
                self.cpp_info.frameworks = ["{dep}_frameworks"]
                self.cpp_info.frameworkdirs = ["{dep}_frameworkdirs"]
                self.cpp_info.defines = ["{dep}_defines"]
                self.cpp_info.cxxflags = ["{dep}_cxxflags"]
                self.cpp_info.cflags = ["{dep}_cflags"]
                self.cpp_info.sharedlinkflags = ["{dep}_sharedlinkflags"]
                self.cpp_info.exelinkflags = ["{dep}_exelinkflags"]
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout

        class ExampleConanIntegration(ConanFile):
            generators = 'SConsDeps'
            requires = 'dep1/0.1', 'dep2/0.1'
        """)

    c = TestClient()
    c.save({"dep1/conanfile.py": dep.format(dep="dep1"),
            "dep2/conanfile.py": dep.format(dep="dep2"),
            "consumer/conanfile.py": consumer})
    c.run("create dep1")
    c.run("create dep2")
    c.run("install consumer")
    sconsdeps = c.load("consumer/SConscript_conandeps")

    # remove all cache paths from the output but the last component
    def clean_paths(text):
        text = text.replace("\\", "/")
        pattern = r"'[A-Za-z]?[:]?[/]?[^']+/([^'/]+)'"
        return re.sub(pattern, r"'\1'", text)

    expected_content = ["""
        "conandeps" : {
            "CPPPATH"     : ['dep2_includedir', 'dep1_includedir'],
            "LIBPATH"     : ['dep2_libdir', 'dep1_libdir'],
            "BINPATH"     : ['dep2_bindir', 'dep1_bindir'],
            "LIBS"        : ['dep2_lib', 'dep1_lib'],
            "FRAMEWORKS"  : ['dep2_frameworks', 'dep1_frameworks'],
            "FRAMEWORKPATH" : ['dep2_frameworkdirs', 'dep1_frameworkdirs'],
            "CPPDEFINES"  : ['dep2_defines', 'dep1_defines'],
            "CXXFLAGS"    : ['dep2_cxxflags', 'dep1_cxxflags'],
            "CCFLAGS"     : ['dep2_cflags', 'dep1_cflags'],
            "SHLINKFLAGS" : ['dep2_sharedlinkflags', 'dep1_sharedlinkflags'],
            "LINKFLAGS"   : ['dep2_exelinkflags', 'dep1_exelinkflags'],
        },
        """, """
        "dep1" : {
            "CPPPATH"     : ['dep1_includedir'],
            "LIBPATH"     : ['dep1_libdir'],
            "BINPATH"     : ['dep1_bindir'],
            "LIBS"        : ['dep1_lib'],
            "FRAMEWORKS"  : ['dep1_frameworks'],
            "FRAMEWORKPATH" : ['dep1_frameworkdirs'],
            "CPPDEFINES"  : ['dep1_defines'],
            "CXXFLAGS"    : ['dep1_cxxflags'],
            "CCFLAGS"     : ['dep1_cflags'],
            "SHLINKFLAGS" : ['dep1_sharedlinkflags'],
            "LINKFLAGS"   : ['dep1_exelinkflags'],
        },
        "dep1_version" : "0.1",
        """, """
        "dep2" : {
            "CPPPATH"     : ['dep2_includedir'],
            "LIBPATH"     : ['dep2_libdir'],
            "BINPATH"     : ['dep2_bindir'],
            "LIBS"        : ['dep2_lib'],
            "FRAMEWORKS"  : ['dep2_frameworks'],
            "FRAMEWORKPATH" : ['dep2_frameworkdirs'],
            "CPPDEFINES"  : ['dep2_defines'],
            "CXXFLAGS"    : ['dep2_cxxflags'],
            "CCFLAGS"     : ['dep2_cflags'],
            "SHLINKFLAGS" : ['dep2_sharedlinkflags'],
            "LINKFLAGS"   : ['dep2_exelinkflags'],
        },
        "dep2_version" : "0.1",
        """]

    clean_sconsdeps = clean_paths(sconsdeps)
    for block in expected_content:
        assert block in clean_sconsdeps
