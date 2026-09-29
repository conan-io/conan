import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.fixture()
def client():
    """ A "hello" package that exports a prebuilt object file in a component, no libraries at all
    """
    c = TestClient()
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(hello C)
        add_library(hello OBJECT hello.c)
        install(FILES $<TARGET_OBJECTS:hello> DESTINATION lib)
        install(FILES hello.h DESTINATION include)
        """)
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Hello(ConanFile):
            name = "hello"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "CMakeLists.txt", "hello.c", "hello.h"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                # The name of the object file depends on the compiler (hello.c.o, hello.obj, ...)
                objs = os.listdir(os.path.join(self.package_folder, "lib"))
                assert len(objs) == 1, f"Unexpected objects {objs}"
                self.cpp_info.components["say"].objects = [os.path.join("lib", objs[0])]
        """)
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmakelists,
            "hello.c": '#include <stdio.h>\n#include "hello.h"\n'
                       'void hello(void) { printf("Hello Objects!\\n"); }\n',
            "hello.h": "void hello(void);\n"})
    c.run("create .")
    return c


def _consumer(requires, targets):
    cmakelists = textwrap.dedent(f"""
        cmake_minimum_required(VERSION 3.23)
        project(example C)
        find_package({requires} REQUIRED CONFIG)
        add_executable(example main.c)
        target_link_libraries(example {targets})
        """)
    conanfile = textwrap.dedent(f"""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Consumer(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeConfigDeps", "CMakeToolchain"
            requires = "{requires}/1.0"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.path.join(self.cpp.build.bindir, "example"), env="conanrun")
        """)
    return {"consumer/conanfile.py": conanfile,
            "consumer/CMakeLists.txt": cmakelists,
            "consumer/main.c": '#include "hello.h"\nint main(void) { hello(); return 0; }\n'}


@pytest.mark.tool("cmake", "3.27")
@pytest.mark.parametrize("targets", ["hello::hello",  # the root target aggregating components
                                     "hello::say",  # the component owning the objects
                                     # both, the object must not be duplicated in the link line
                                     "hello::hello hello::say"])
def test_objects_direct_consumer(client, targets):
    """ the object files of a direct dependency end in the link line of the consumer """
    c = client
    c.save(_consumer("hello", targets))
    c.run("build consumer")
    assert "Hello Objects!" in c.out


@pytest.mark.tool("cmake", "3.27")
def test_objects_transitive_consumer(client):
    """ CMake only adds the objects of a target to the link line of its *direct* consumers, the
    Conan target forwards them with $<TARGET_OBJECTS:...>, so linking "middle::middle" is enough
    """
    c = client
    middle = textwrap.dedent("""
        from conan import ConanFile
        class Middle(ConanFile):
            name = "middle"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires("hello/1.0", transitive_headers=True, transitive_libs=True)

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libdirs = []
                self.cpp_info.requires = ["hello::say"]
        """)
    c.save({"middle/conanfile.py": middle})
    c.run("create middle")

    c.save(_consumer("middle", "middle::middle"))
    c.run("build consumer")
    assert "Hello Objects!" in c.out
