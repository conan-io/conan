import pytest
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.test.assets.sources import gen_function_cpp, gen_function_h


def test_module_project():
    # app ---> module1 ---> mylib

    client = TestClient()

    # -- Generate MyLib
    cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(MyLib CXX)

            add_library(MyLib mylib.h mylib.cpp)
            install(FILES mylib.h DESTINATION include)
            install(TARGETS MyLib DESTINATION "."
                RUNTIME DESTINATION bin
                ARCHIVE DESTINATION lib
                LIBRARY DESTINATION lib
                )
            """)

    conanfile = textwrap.dedent("""
                from conan import ConanFile
                from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout


                class pkgRecipe(ConanFile):
                    name = "mylib"
                    package_type = "library"

                    settings = "os", "compiler", "build_type", "arch"
                    options = {
                        "shared": [True, False],
                        "fPIC": [True, False],
                    }
                    default_options = {
                        "shared": True,
                        "fPIC": True,
                    }
                    implements = ["auto_shared_fpic"]

                    exports_sources = "CMakeLists.txt", "mylib.h", "mylib.cpp"

                    def layout(self):
                        cmake_layout(self)

                    def generate(self):
                        tc = CMakeToolchain(self)
                        tc.generate()

                    def build(self):
                        cmake = CMake(self)
                        cmake.configure()
                        cmake.build()

                    def package(self):
                        cmake = CMake(self)
                        cmake.install()

                    def package_info(self):
                        self.cpp_info.libs = ["MyLib"]
            """)

    client.save({"mylib/conanfile.py": conanfile,
                 "mylib/mylib.h": gen_function_h(name="mylib"),
                 "mylib/mylib.cpp": gen_function_cpp(name="mylib"),
                 "mylib/CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("create mylib --version=0.1 -o='*/*:shared=True'")

    # -- Generate MyModule
    cmakelists = textwrap.dedent("""
                cmake_minimum_required(VERSION 3.15)
                project(MyModule CXX)

                find_package(mylib REQUIRED)

                add_library(MyModule MODULE main.cpp)
                target_link_libraries(MyModule mylib::mylib)

                install(TARGETS MyModule DESTINATION "."
                RUNTIME DESTINATION bin
                ARCHIVE DESTINATION lib
                LIBRARY DESTINATION lib
                )
                """)

    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps


            class pkgRecipe(ConanFile):
                name = "mymodule"
                package_type = "module"

                settings = "os", "compiler", "build_type", "arch"
                options = {
                    "shared": [True, False],
                    "fPIC": [True, False],
                }
                default_options = {
                    "shared": False,
                    "fPIC": True,
                }
                implements = ["auto_shared_fpic"]

                exports_sources = "CMakeLists.txt", "main.cpp"

                def layout(self):
                    cmake_layout(self)

                def generate(self):
                    deps = CMakeDeps(self)
                    deps.generate()
                    tc = CMakeToolchain(self)
                    tc.generate()

                def requirements(self):
                    self.requires("mylib/0.1")

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()

                def package_info(self):
                    self.cpp_info.bindirs.append("lib")
        """)
    cpp = textwrap.dedent("""

    #include <iostream>
    #include "mylib.h"

    #ifdef _WIN32
        #define DLL_EXPORT __declspec(dllexport)
    #else
        #define DLL_EXPORT
    #endif

    extern "C" DLL_EXPORT int moduleFunction(){
        mylib();
        return 0;
    }
    """)

    client.save({"mymodule/conanfile.py": conanfile,
                 "mymodule/main.cpp": cpp,
                 "mymodule/CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("create mymodule --version=0.1 -v -c tools.cmake.cmakedeps:new='will_break_next'")


    # -- Generate Main app
    cmake = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
            project(MainApp CXX)

            add_executable(MainApp main.cpp)
            install(TARGETS MainApp DESTINATION "."
                RUNTIME DESTINATION bin
                ARCHIVE DESTINATION lib
                LIBRARY DESTINATION lib
                )
    """)
    app_cpp = textwrap.dedent("""
                #include <iostream>
                #ifdef _WIN32
                #include <windows.h>
                #else
                #include <dlfcn.h>
                #endif

                int main() {
                    std::cout << "Hello from App" << std::endl;


                    #ifdef _WIN32

                    typedef int (__cdecl *MYPROC)();
                    HINSTANCE hinstLib = LoadLibrary(TEXT("MyModule.dll"));
                    if (!hinstLib){
                        std::cerr << "Error loading plugin: " << __FILE__ << __LINE__ << std::endl;
                        return 1;
                    }
                    MYPROC ProcAdd = (MYPROC) GetProcAddress(hinstLib, "moduleFunction");
                    if (!ProcAdd) {
                        std::cerr << "Error finding function 'moduleFunction': " << __FILE__ << __LINE__ << std::endl;
                        FreeLibrary(hinstLib);
                        return 1;
                    }
                    (ProcAdd)();
                    FreeLibrary(hinstLib);

                    #else
                    void* handle = dlopen("libMyModule.so", RTLD_LAZY);
                    if (!handle) {
                        std::cerr << "Error loading plugin: " << dlerror() << std::endl;
                        return 1;
                    }

                    typedef int (*moduleFunction)(void);
                    moduleFunction customFunction;
                    *(void**)(&customFunction) = dlsym(handle, "moduleFunction");

                    if (!customFunction) {
                        std::cerr << "Error finding function 'moduleFunction': " << dlerror() << std::endl;
                        dlclose(handle);
                        return 1;
                    }

                    customFunction();
                    dlclose(handle);
                    #endif

                    return 0;
                }
                """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps
        import os


        class pkgRecipe(ConanFile):
            name = "mainapp"
            package_type = "application"

            settings = "os", "compiler", "build_type", "arch"

            exports_sources = "CMakeLists.txt", "main.cpp"

            def layout(self):
                cmake_layout(self)

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

            def requirements(self):
                self.requires("mymodule/0.1")

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                if self.settings.os == "Windows":
                    my_path = self.cpp.build.bindir
                    self.run(os.path.join(my_path, "MainApp"), env="conanrun")
                else:
                    self.run(f"'{os.path.join(self.build_folder, 'MainApp')}'", env="conanrun")
    """)
    client.save(
        {"mainapp/conanfile.py": conanfile,
         "mainapp/main.cpp": app_cpp,
         "mainapp/CMakeLists.txt": cmake}, clean_first=True)
    client.run("create mainapp --version=0.1 -c tools.cmake.cmakedeps:new='will_break_next'")
    assert "mylib: Release!" in client.out
