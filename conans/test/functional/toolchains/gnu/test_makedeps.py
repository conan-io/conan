import textwrap

import platform
import pytest

from conans.test.assets.autotools import gen_makefile
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient
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


@pytest.mark.tool("cmake")
def test_makedeps_with_tool_requires():
    """
    MakeDeps has to create any test requires to be declared on the recipe.
    """
    client = TestClient(path_with_spaces=False)
    with client.chdir("lib"):
        client.run("new cmake_lib -d name=app -d version=1.0")
        client.run("create . -tf=\"\"")
    with client.chdir("test"):
        client.run("new cmake_lib -d name=test -d version=1.0")
        client.run("create . -tf=\"\"")
    with client.chdir("tool"):
        client.run("new cmake_lib -d name=tool -d version=1.0")
        client.run("create . -tf=\"\"")
    # Create library having build and test requires
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.test_requires('app/1.0')
                self.test_requires('test/1.0')
                self.tool_requires('tool/1.0')
        ''')
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g MakeDeps")
    content = client.load(CONAN_MAKEFILE_FILENAME)
    assert "CONAN_NAME_TEST" in content
    assert "CONAN_NAME_APP" in content


@pytest.mark.tool("make" if platform.system() != "Windows" else "msys2")
@pytest.mark.tool("cmake")
def test_makedeps_with_makefile_build():
    """
    Build a small application using MakeDeps generator
    """
    client = TestClient(path_with_spaces=False)
    with client.chdir("lib"):

        client.run("new cmake_lib -d name=hello -d version=0.1.0")
        client.run(r'create . -tf="" -pr:b=default -pr:h=default')
    with client.chdir("app"):
        client.run("install --requires=hello/0.1.0 -pr:b=default -pr:h=default -g MakeDeps -of build")
        client.save({"Makefile": textwrap.dedent('''
            include build/conandeps.mk

            CFLAGS              += $(CONAN_CFLAGS)
            CXXFLAGS            += $(CONAN_CXXFLAGS) -std=c++14
            CPPFLAGS            += $(addprefix -I, $(CONAN_INCLUDE_DIRS))
            CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
            LDFLAGS             += $(addprefix -L, $(CONAN_LIB_DIRS))
            LDLIBS              += $(addprefix -l, $(CONAN_LIBS))
            EXELINKFLAGS        += $(CONAN_EXELINKFLAGS)

            SRCS          = main.cpp
            OBJS          = main.o
            EXE_FILENAME  = main

            .PHONY                  :   exe
            exe                     :   $(EXE_FILENAME)

            $(EXE_FILENAME)         :   $(OBJS)
            \t$(CXX) $(OBJS) $(CXXFLAGS) $(LDFLAGS) $(LDLIBS) -o $(EXE_FILENAME)

            %.o                     :   $(SRCS)
            \t$(CXX) -c $(CPPFLAGS) $(CXXFLAGS) $< -o $@
            '''),
            "main.cpp": textwrap.dedent(r'''
            #include "hello.h"
            int main() { hello(); }
            ''')})
        client.run_command("make -f Makefile")
