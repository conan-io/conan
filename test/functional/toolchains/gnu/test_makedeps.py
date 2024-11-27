import textwrap

import platform
import pytest

from conan.test.assets.autotools import gen_makefile
from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.tools import TestClient
from conan.tools.gnu.makedeps import CONAN_MAKEFILE_FILENAME


@pytest.mark.tool("make" if platform.system() != "Windows" else "msys2")
def test_make_deps_definitions_escape():
    """
    MakeDeps has to escape the definitions properly.
    """
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("USER_CONFIG=\"user_config.h\"")
                self.cpp_info.defines.append('OTHER="other.h"')
                self.cpp_info.cflags.append("flag1=\"my flag1\"")
                self.cpp_info.cxxflags.append('flag2="my flag2"')
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . --name=hello --version=0.1.0")
    client.run("install --requires=hello/0.1.0 --build=missing -g MakeDeps")
    client.run_command(f"make --print-data-base -f {CONAN_MAKEFILE_FILENAME}", assert_error=True)
    assert r'CONAN_CXXFLAGS_HELLO = flag2=\"my flag2\"' in client.out
    assert r'CONAN_CFLAGS_HELLO = flag1=\"my flag1\"' in client.out
    assert r'CONAN_DEFINES_HELLO = $(CONAN_DEFINE_FLAG)USER_CONFIG="user_config.h" $(CONAN_DEFINE_FLAG)OTHER="other.h"' in client.out


def test_makedeps_with_tool_requires():
    """
    MakeDeps has to create any test requires to be declared on the recipe.
    """
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.libs = [self.name]
        ''')
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=hello --version=0.1.0")
    client.run("create . --name=test --version=0.1.0")
    client.run("create . --name=tool --version=0.1.0")
    # Create library having build and test requires
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.test_requires('hello/0.1.0')
                self.test_requires('test/0.1.0')
                self.tool_requires('tool/0.1.0')
        ''')
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g MakeDeps")
    content = client.load(CONAN_MAKEFILE_FILENAME)
    assert "CONAN_NAME_TEST" in content
    assert "CONAN_NAME_HELLO" in content
    assert "CONAN_NAME_TOOL" not in content


@pytest.mark.tool("make" if platform.system() != "Windows" else "msys2")
def test_makedeps_with_makefile_build():
    """
    Build a small application using MakeDeps generator and with components
    """
    client = TestClient(path_with_spaces=False)
    with client.chdir("lib"):
        client.save({"Makefile": gen_makefile(libs=["hello"]),
                    "hello.cpp": gen_function_cpp(name="hello", includes=["hello"], calls=["hello"]),
                    "hello.h": gen_function_h(name="hello"),
                    "conanfile.py": textwrap.dedent(r'''
                    from conan import ConanFile
                    from conan.tools.gnu import Autotools
                    from conan.tools.files import copy
                    import os
                    class PackageConan(ConanFile):
                        exports_sources = ("Makefile", "hello.cpp", "hello.h")
                        settings = "os", "arch", "compiler"

                        def configure(self):
                            self.win_bash = self.settings.os == "Windows"

                        def build(self):
                            self.run("make -f Makefile")

                        def package(self):
                            copy(self, "libhello.a", src=self.build_folder, dst=os.path.join(self.package_folder, "lib"))
                            copy(self, "hello.h", src=self.source_folder, dst=os.path.join(self.package_folder, "include"))

                        def package_info(self):
                            self.cpp_info.components["qux"].includedirs = ["include"]
                            self.cpp_info.components["baz"].libs = ["hello"]
                            self.cpp_info.components["baz"].defines = ["FOOBAR=1"]
                    ''')
                     })
        client.run('create . --name=hello --version=0.1.0 -c tools.microsoft.bash:subsystem=msys2 -c tools.microsoft.bash:path=bash')
    with client.chdir("global"):
        # Consume from global variables
        client.run("install --requires=hello/0.1.0 -pr:b=default -pr:h=default -g MakeDeps -of build")
        client.save({"Makefile": textwrap.dedent('''
            include build/conandeps.mk
            CXXFLAGS            += $(CONAN_CXXFLAGS)
            CPPFLAGS            += $(addprefix -I, $(CONAN_INCLUDE_DIRS))
            CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
            LDFLAGS             += $(addprefix -L, $(CONAN_LIB_DIRS))
            LDLIBS              += $(addprefix -l, $(CONAN_LIBS))
            EXELINKFLAGS        += $(CONAN_EXELINKFLAGS)

            all:
            \t$(CXX) main.cpp $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) $(LDLIBS) $(EXELINKFLAGS) -o main
            '''),
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
            })
        client.run_command("make -f Makefile")
    with client.chdir("components"):
        # Consume from components
        client.run("install --requires=hello/0.1.0 -pr:b=default -pr:h=default -g MakeDeps -of build")
        client.save({"Makefile": textwrap.dedent('''
            include build/conandeps.mk
            CXXFLAGS            += $(CONAN_CXXFLAGS)
            CPPFLAGS            += $(addprefix -I, $(CONAN_INCLUDE_DIRS_HELLO_QUX))
            CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES) $(CONAN_DEFINES_HELLO_BAZ))
            LDFLAGS             += $(addprefix -L, $(CONAN_LIB_DIRS_HELLO_BAZ))
            LDLIBS              += $(addprefix -l, $(CONAN_LIBS_HELLO_BAZ))
            EXELINKFLAGS        += $(CONAN_EXELINKFLAGS)

            all:
            \t$(CXX) main.cpp $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) $(LDLIBS) $(EXELINKFLAGS) -o main
            '''),
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
            })
        client.run_command("make -f Makefile")
