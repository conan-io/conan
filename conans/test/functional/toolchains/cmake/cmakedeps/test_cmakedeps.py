import os
import platform
import textwrap

import pytest

from conans.client.tools import replace_in_file
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.pkg_cmake import pkg_cmake
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os
        class Pkg(ConanFile):
            settings = "build_type", "os", "arch", "compiler"
            {}
            def package(self):
                save(os.path.join(self.package_folder, "include", "%s.h" % self.name),
                     '#define MYVAR%s "%s"' % (self.name, self.settings.build_type))
        """)

    c.save({"conanfile.py": conanfile.format("")})
    c.run("create . liba/0.1@ -s build_type=Release")
    c.run("create . liba/0.1@ -s build_type=Debug")
    c.save({"conanfile.py": conanfile.format("requires = 'liba/0.1'")})
    c.run("create . libb/0.1@ -s build_type=Release")
    c.run("create . libb/0.1@ -s build_type=Debug")
    return c


@pytest.mark.tool_cmake
def test_transitive_multi(client):
    # TODO: Make a full linking example, with correct header transitivity

    # Save conanfile and example
    conanfile = textwrap.dedent("""
        [requires]
        libb/0.1

        [generators]
        CMakeDeps
        CMakeToolchain
        """)
    example_cpp = gen_function_cpp(name="main", includes=["libb", "liba"],
                                   preprocessor=["MYVARliba", "MYVARlibb"])
    client.save({"conanfile.txt": conanfile,
                 "CMakeLists.txt": gen_cmakelists(appname="example",
                                                  appsources=["example.cpp"], find_package=["libb"]),
                 "example.cpp": example_cpp}, clean_first=True)

    with client.chdir("build"):
        for bt in ("Debug", "Release"):
            client.run("install .. user/channel -s build_type={}".format(bt))

        # Test that we are using find_dependency with the NO_MODULE option
        # to skip finding first possible FindBye somewhere
        assert "find_dependency(${_DEPENDENCY} REQUIRED ${${_DEPENDENCY}_FIND_MODE})" \
               in client.load("libb-config.cmake")
        arch = client.get_default_host_profile().settings['arch']
        assert 'set(liba_FIND_MODE "NO_MODULE")' in client.load(f"libb-release-{arch}-data.cmake")

        if platform.system() == "Windows":
            client.run_command('cmake .. -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake')
            client.run_command('cmake --build . --config Debug')
            client.run_command('cmake --build . --config Release')

            client.run_command('Debug\\example.exe')
            assert "main: Debug!" in client.out
            assert "MYVARliba: Debug" in client.out
            assert "MYVARlibb: Debug" in client.out

            client.run_command('Release\\example.exe')
            assert "main: Release!" in client.out
            assert "MYVARliba: Release" in client.out
            assert "MYVARlibb: Release" in client.out
        else:
            # The CMakePresets IS MESSING WITH THE BUILD TYPE and then ignores the -D so I remove it
            replace_in_file(os.path.join(client.current_folder, "CMakePresets.json"),
                            "CMAKE_BUILD_TYPE", "DONT_MESS_WITH_BUILD_TYPE")
            for bt in ("Debug", "Release"):
                client.run_command('cmake .. -DCMAKE_BUILD_TYPE={} '
                                   '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake'.format(bt))
                client.run_command('cmake --build . --clean-first')

                client.run_command('./example')
                assert "main: {}!".format(bt) in client.out
                assert "MYVARliba: {}".format(bt) in client.out
                assert "MYVARlibb: {}".format(bt) in client.out


@pytest.mark.tool_cmake
def test_system_libs():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class Test(ConanFile):
            name = "Test"
            version = "0.1"
            settings = "build_type"
            def package(self):
                save(os.path.join(self.package_folder, "lib/lib1.lib"), "")
                save(os.path.join(self.package_folder, "lib/liblib1.a"), "")

            def package_info(self):
                self.cpp_info.libs = ["lib1"]
                if self.settings.build_type == "Debug":
                    self.cpp_info.system_libs.append("sys1d")
                else:
                    self.cpp_info.system_libs.append("sys1")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")

    conanfile = textwrap.dedent("""
        [requires]
        Test/0.1

        [generators]
        CMakeDeps
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer NONE)
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
        find_package(Test)
        message("System libs release: ${Test_SYSTEM_LIBS_RELEASE}")
        message("Libraries to Link release: ${Test_LIBS_RELEASE}")
        message("System libs debug: ${Test_SYSTEM_LIBS_DEBUG}")
        message("Libraries to Link debug: ${Test_LIBS_DEBUG}")
        get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
        message("Target libs: ${tmp}")
        get_target_property(tmp CONAN_LIB::Test_lib1_%s INTERFACE_LINK_LIBRARIES)
        message("Micro-target libs: ${tmp}")
        get_target_property(tmp Test_DEPS_TARGET INTERFACE_LINK_LIBRARIES)
        message("Micro-target deps: ${tmp}")
        """)

    for build_type in ["Release", "Debug"]:
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmakelists % build_type.upper()}, clean_first=True)
        client.run("install conanfile.txt -s build_type=%s" % build_type)
        client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

        library_name = "sys1d" if build_type == "Debug" else "sys1"
        # FIXME: Note it is CONAN_LIB::Test_lib1_RELEASE, not "lib1" as cmake_find_package
        if build_type == "Release":
            assert "System libs release: %s" % library_name in client.out
            assert "Libraries to Link release: lib1" in client.out
        else:
            assert "System libs debug: %s" % library_name in client.out
            assert "Libraries to Link debug: lib1" in client.out

        assert f"Target libs: $<$<CONFIG:{build_type}>:>;$<$<CONFIG:{build_type}>:CONAN_LIB::Test_lib1_{build_type.upper()}>" in client.out
        assert "Micro-target libs: Test_DEPS_TARGET" in client.out
        micro_target_deps = f"Micro-target deps: $<$<CONFIG:{build_type}>:>;$<$<CONFIG:{build_type}>:{library_name}>;" \
                            f"$<$<CONFIG:{build_type}>:>"
        assert micro_target_deps in client.out


@pytest.mark.tool_cmake
def test_system_libs_no_libs():
    """If the recipe doesn't declare cpp_info.libs then the target with the system deps, frameworks
       and transitive deps has to be linked to the global target"""
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class Test(ConanFile):
            name = "Test"
            version = "0.1"
            settings = "build_type"

            def package_info(self):
                if self.settings.build_type == "Debug":
                    self.cpp_info.system_libs.append("sys1d")
                else:
                    self.cpp_info.system_libs.append("sys1")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")

    conanfile = textwrap.dedent("""
        [requires]
        Test/0.1

        [generators]
        CMakeDeps
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer NONE)
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
        find_package(Test)
        message("System libs Release: ${Test_SYSTEM_LIBS_RELEASE}")
        message("Libraries to Link release: ${Test_LIBS_RELEASE}")
        message("System libs Debug: ${Test_SYSTEM_LIBS_DEBUG}")
        message("Libraries to Link debug: ${Test_LIBS_DEBUG}")
        get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
        message("Target libs: ${tmp}")
        get_target_property(tmp Test_DEPS_TARGET INTERFACE_LINK_LIBRARIES)
        message("DEPS TARGET: ${tmp}")

        """)

    for build_type in ["Release", "Debug"]:
        client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
        client.run("install conanfile.txt -s build_type=%s" % build_type)
        client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

        library_name = "sys1d" if build_type == "Debug" else "sys1"

        assert f"System libs {build_type}: {library_name}" in client.out
        assert f"Target libs: $<$<CONFIG:{build_type}>:>;$<$<CONFIG:{build_type}>:>;Test_DEPS_TARGET" in client.out
        assert f"DEPS TARGET: $<$<CONFIG:{build_type}>:>;" \
               f"$<$<CONFIG:{build_type}>:{library_name}>" in client.out


@pytest.mark.tool_cmake
def test_system_libs_components_no_libs():
    """If the recipe doesn't declare cpp_info.libs then the target with the system deps, frameworks
       and transitive deps has to be linked to the component target"""
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class Test(ConanFile):
            name = "Test"
            version = "0.1"
            settings = "build_type"

            def package_info(self):
                if self.settings.build_type == "Debug":
                    self.cpp_info.components["foo"].system_libs.append("sys1d")
                else:
                    self.cpp_info.components["foo"].system_libs.append("sys1")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")

    conanfile = textwrap.dedent("""
        [requires]
        Test/0.1

        [generators]
        CMakeDeps
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer NONE)
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
        find_package(Test)
        message("System libs Release: ${Test_Test_foo_SYSTEM_LIBS_RELEASE}")
        message("Libraries to Link release: ${Test_Test_foo_LIBS_RELEASE}")
        message("System libs Debug: ${Test_Test_foo_SYSTEM_LIBS_DEBUG}")
        message("Libraries to Link debug: ${Test_Test_foo_LIBS_DEBUG}")

        get_target_property(tmp Test::foo INTERFACE_LINK_LIBRARIES)
        message("Target libs: ${tmp}")
        get_target_property(tmp Test_Test_foo_DEPS_TARGET INTERFACE_LINK_LIBRARIES)
        message("DEPS TARGET: ${tmp}")

        """)

    for build_type in ["Release", "Debug"]:
        client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
        client.run("install conanfile.txt -s build_type=%s" % build_type)
        client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

        library_name = "sys1d" if build_type == "Debug" else "sys1"

        assert f"System libs {build_type}: {library_name}" in client.out
        assert f"Target libs: $<$<CONFIG:{build_type}>:>;$<$<CONFIG:{build_type}>:>;Test_Test_foo_DEPS_TARGET" in client.out
        assert f"DEPS TARGET: $<$<CONFIG:{build_type}>:>;" \
               f"$<$<CONFIG:{build_type}>:{library_name}>" in client.out


@pytest.mark.tool_cmake
def test_do_not_mix_cflags_cxxflags():
    # TODO: Verify with components too
    client = TestClient()
    cpp_info = {"cflags": ["one", "two"], "cxxflags": ["three", "four"]}
    client.save({"conanfile.py": GenConanfile("upstream", "1.0").with_package_info(cpp_info=cpp_info,
                                                                                   env_info={})})
    client.run("create .")

    consumer_conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            requires = "upstream/1.0"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
       cmake_minimum_required(VERSION 3.15)
       project(consumer NONE)
       find_package(upstream CONFIG REQUIRED)
       get_target_property(tmp upstream::upstream INTERFACE_COMPILE_OPTIONS)
       message("compile options: ${tmp}")
       message("cflags: ${upstream_COMPILE_OPTIONS_C_RELEASE}")
       message("cxxflags: ${upstream_COMPILE_OPTIONS_CXX_RELEASE}")
       """)
    client.save({"conanfile.py": consumer_conanfile,
                 "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("create .")
    assert "compile options: $<$<CONFIG:Release>:" \
           "$<$<COMPILE_LANGUAGE:CXX>:three;four>;$<$<COMPILE_LANGUAGE:C>:one;two>>" in client.out
    assert "cflags: one;two" in client.out
    assert "cxxflags: three;four" in client.out


def test_custom_configuration(client):
    """  The configuration may differ from the build context and the host context"""
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conan.tools.cmake import CMakeDeps

       class Consumer(ConanFile):
           name = "consumer"
           version = "1.0"
           settings = "os", "compiler", "arch", "build_type"
           requires = "liba/0.1"
           build_requires = "liba/0.1"
           generators = "CMakeToolchain"

           def generate(self):
               cmake = CMakeDeps(self)
               cmake.configuration = "Debug"
               cmake.build_context_activated = ["liba"]
               cmake.build_context_suffix["liba"] = "_build"
               cmake.generate()
       """)
    host_arch = client.get_default_host_profile().settings['arch']
    client.save({"conanfile.py": conanfile})
    client.run("install . -pr:h default -s:b build_type=RelWithDebInfo"
               " -pr:b default -s:b arch=x86 --build missing")
    curdir = client.current_folder
    data_name_context_build = "liba_build-relwithdebinfo-x86-data.cmake"
    data_name_context_host = f"liba-debug-{host_arch}-data.cmake"
    assert os.path.exists(os.path.join(curdir, data_name_context_build))
    assert os.path.exists(os.path.join(curdir, data_name_context_host))

    assert "set(liba_build_INCLUDE_DIRS_RELWITHDEBINFO" in \
           open(os.path.join(curdir, data_name_context_build)).read()
    assert "set(liba_INCLUDE_DIRS_DEBUG" in \
           open(os.path.join(curdir, data_name_context_host)).read()


def test_buildirs_working():
    """  If a recipe declares cppinfo.buildirs those dirs will be exposed to be consumer
    to allow a cmake "include" function call after a find_package"""
    c = TestClient()
    conanfile = str(GenConanfile().with_name("my_lib").with_version("1.0")
                                  .with_import("import os").with_import("from conans import tools"))
    conanfile += """
    def package(self):
        tools.save(os.path.join(self.package_folder, "my_build_dir", "my_cmake_script.cmake"),
                   'set(MYVAR "Like a Rolling Stone")')

    def package_info(self):
        self.cpp_info.builddirs=["my_build_dir"]
    """

    c.save({"conanfile.py": conanfile})
    c.run("create .")

    consumer_conanfile = GenConanfile().with_name("consumer").with_version("1.0")\
        .with_cmake_build().with_require("my_lib/1.0") \
        .with_settings("os", "arch", "build_type", "compiler") \
        .with_exports_sources("*.txt")
    cmake = gen_cmakelists(find_package=["my_lib"])
    cmake += """
    message("CMAKE_MODULE_PATH: ${CMAKE_MODULE_PATH}")
    include("my_cmake_script")
    message("MYVAR=>${MYVAR}")
    """
    c.save({"conanfile.py": consumer_conanfile, "CMakeLists.txt": cmake})
    c.run("create .")
    assert "MYVAR=>Like a Rolling Stone" in c.out


@pytest.mark.tool_cmake
def test_cpp_info_link_objects():
    client = TestClient()
    obj_ext = "obj" if platform.system() == "Windows" else "o"
    cpp_info = {"objects": [os.path.join("lib", "myobject.{}".format(obj_ext))]}
    object_cpp = gen_function_cpp(name="myobject")
    object_h = gen_function_h(name="myobject")
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyObject)
        file(GLOB HEADERS *.h)
        add_library(myobject OBJECT myobject.cpp)
        if( WIN32 )
            set(OBJ_PATH "myobject.dir/Release/myobject${CMAKE_C_OUTPUT_EXTENSION}")
        else()
            set(OBJ_PATH "CMakeFiles/myobject.dir/myobject.cpp${CMAKE_C_OUTPUT_EXTENSION}")
        endif()
        install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${OBJ_PATH}
                DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
                RENAME myobject${CMAKE_C_OUTPUT_EXTENSION})
        install(FILES ${HEADERS}
                DESTINATION ${CMAKE_INSTALL_PREFIX}/include)
    """)

    test_package_cpp = gen_function_cpp(name="main", includes=["myobject"], calls=["myobject"])
    test_package_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(example)
        find_package(myobject REQUIRED)
        add_executable(example example.cpp)
        target_link_libraries(example myobject::myobject)
    """)

    client.save({"CMakeLists.txt": cmakelists,
                 "conanfile.py": GenConanfile("myobject", "1.0").with_package_info(cpp_info=cpp_info,
                                                                                   env_info={})
                                                                .with_exports_sources("*")
                                                                .with_cmake_build()
                                                                .with_package("cmake = CMake(self)",
                                                                              "cmake.install()"),
                 "myobject.cpp": object_cpp,
                 "myobject.h": object_h,
                 "test_package/conanfile.py": GenConanfile().with_cmake_build()
                                                            .with_import("import os")
                                                            .with_test('path = "{}".format(self.settings.build_type) '
                                                                       'if self.settings.os == "Windows" else "."')
                                                            .with_test('self.run("{}{}example".format(path, os.sep))'),
                 "test_package/example.cpp": test_package_cpp,
                 "test_package/CMakeLists.txt": test_package_cmakelists})

    client.run("create . -s build_type=Release")
    assert "myobject: Release!" in client.out


def test_private_transitive():
    # https://github.com/conan-io/conan/issues/9514
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_require("dep/0.1", private=True),
                 "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                        .with_settings("os", "build_type", "arch")})
    client.run("create dep dep/0.1@")
    client.run("create pkg pkg/0.1@")
    client.run("install consumer -g CMakeDeps -s arch=x86_64 -s build_type=Release")
    assert "dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip" in client.out
    data_cmake = client.load("pkg-release-x86_64-data.cmake")
    assert 'set(pkg_FIND_DEPENDENCY_NAMES "")' in data_cmake


@pytest.mark.tool_cmake
def test_system_dep():
    """This test creates a zlib package and use the installation CMake FindZLIB.cmake to locate
    the library of the package. That happens because:
    - The package declares: self.cpp_info.set_property("cmake_find_mode", "none") so CMakeDeps does nothing
    - The toolchain set the CMAKE_LIBRARY_PATH to the "lib" of the package, so the library file is found
    """
    client = TestClient()
    files = pkg_cmake("zlib", "0.1")
    files["conanfile.py"] += """
    def package_info(self):
        # This will use the FindZLIB from CMake but will find this library package
        self.cpp_info.set_property("cmake_file_name", "ZLIB")
        self.cpp_info.set_property("cmake_target_name", "ZLIB::ZLIB")
        self.cpp_info.set_property("cmake_find_mode", "none")
    """
    client.save({os.path.join("zlib", name): content for name, content in files.items()})
    files = pkg_cmake("mylib", "0.1", requires=["zlib/0.1"])
    files["CMakeLists.txt"] = files["CMakeLists.txt"].replace("find_package(zlib)",
                                                              "find_package(ZLIB)")
    files["CMakeLists.txt"] = files["CMakeLists.txt"].replace("zlib::zlib","ZLIB::ZLIB")
    client.save({os.path.join("mylib", name): content for name, content in files.items()})
    files = pkg_cmake("consumer", "0.1", requires=["mylib/0.1"])
    client.save({os.path.join("consumer", name): content for name, content in files.items()})
    client.run("create zlib")
    client.run("create mylib")
    client.run("create consumer")
    assert "Found ZLIB:" in client.out

    client.run("install consumer")
    if platform.system() != "Windows":
        host_arch = client.get_default_host_profile().settings['arch']
        data = os.path.join(f"consumer/build/generators/mylib-release-{host_arch}-data.cmake")
        contents = client.load(data)
        assert 'set(ZLIB_FIND_MODE "")' in contents


@pytest.mark.tool_cmake(version="3.19")
def test_error_missing_build_type():
    # https://github.com/conan-io/conan/issues/11168
    client = TestClient()

    client.run("new hello/1.0 -m=cmake_lib")
    client.run("create . -tf=None")

    conanfile = textwrap.dedent("""
        [requires]
        hello/1.0
        [generators]
        CMakeDeps
        CMakeToolchain
    """)

    main = textwrap.dedent("""
        #include <hello.h>
        int main() {hello();return 0;}
    """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(app)
        find_package(hello REQUIRED)
        add_executable(app)
        target_link_libraries(app hello::hello)
        target_sources(app PRIVATE main.cpp)
    """)

    if platform.system() != "Windows":
        client.save({
            "conanfile.txt": conanfile,
            "main.cpp": main,
            "CMakeLists.txt": cmakelists
        }, clean_first=True)

        client.run("install .")
        client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -G 'Unix Makefiles'", assert_error=True)
        assert "Please, set the CMAKE_BUILD_TYPE variable when calling to CMake" in client.out

    client.save({
        "conanfile.txt": conanfile,
        "main.cpp": main,
        "CMakeLists.txt": cmakelists
    }, clean_first=True)

    client.run("install .")

    generator = {
        "Windows": '-G "Visual Studio 15 2017"',
        "Darwin": '-G "Xcode"',
        "Linux": '-G "Ninja Multi-Config"'
    }.get(platform.system())

    client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake {}".format(generator))
    client.run_command("cmake --build . --config Release")
    run_app = r".\Release\app.exe" if platform.system() == "Windows" else "./Release/app"
    client.run_command(run_app)
    assert "Hello World Release!" in client.out
