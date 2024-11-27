import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_build_modules_alias_target():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy

        class Conan(ConanFile):
            name = "hello"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = ["target-alias.cmake"]

            def package(self):
                copy(self, "target-alias.cmake", self.source_folder,
                     os.path.join(self.package_folder, "share/cmake"))

            def package_info(self):
                module = os.path.join("share", "cmake", "target-alias.cmake")
                self.cpp_info.set_property("cmake_build_modules", [module])
        """)

    target_alias = textwrap.dedent("""
        add_library(otherhello INTERFACE IMPORTED)
        target_link_libraries(otherhello INTERFACE hello::hello)
        """)
    client.save({"conanfile.py": conanfile, "target-alias.cmake": target_alias})
    client.run("create .")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = ["CMakeLists.txt"]
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "hello/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.0)
        project(test)
        find_package(hello CONFIG)
        get_target_property(tmp otherhello INTERFACE_LINK_LIBRARIES)
        message("otherhello link libraries: ${tmp}")
        """)
    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")
    assert "otherhello link libraries: hello::hello" in client.out


@pytest.mark.tool("cmake")
def test_build_modules_custom_script():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy

        class Conan(ConanFile):
            name = "myfunctions"
            version = "1.0"
            exports_sources = ["*.cmake"]

            def package(self):
                copy(self, "*.cmake", self.source_folder, self.package_folder)

            def package_info(self):
                self.cpp_info.set_property("cmake_build_modules", ["myfunction.cmake"])
        """)

    myfunction = textwrap.dedent("""
        function(myfunction)
            message("Hello myfunction!!!!")
        endfunction()
        """)
    client.save({"conanfile.py": conanfile, "myfunction.cmake": myfunction})
    client.run("create .")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeDeps

        class Conan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            tool_requires = "myfunctions/1.0"

            def generate(self):
                deps = CMakeDeps(self)
                deps.build_context_activated = ["myfunctions"]
                deps.build_context_build_modules = ["myfunctions"]
                deps.set_property("myfunctions", "cmake_find_mode", "module", build_context=True)
                deps.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.0)
        project(test)
        find_package(myfunctions MODULE REQUIRED)
        myfunction()
        """)
    client.save({"conanfile.py": consumer,
                 "CMakeLists.txt": cmakelists},
                clean_first=True)
    client.run("build .")
    assert "Hello myfunction!!!!" in client.out


@pytest.mark.tool("cmake")
def test_build_modules_components_is_not_possible():
    """
    The "cmake_build_module" property declared in the components is useless
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy

        class Conan(ConanFile):
            name = "openssl"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = ["crypto.cmake", "root.cmake"]

            def package(self):
                copy(self, "*.cmake", self.source_folder, os.path.join(self.package_folder, "share/cmake"))

            def package_info(self):
                crypto_module = os.path.join("share", "cmake", "crypto.cmake")
                self.cpp_info.components["crypto"].set_property("cmake_build_modules", [crypto_module])

                root_module = os.path.join("share", "cmake", "root.cmake")
                self.cpp_info.set_property("cmake_build_modules", [root_module])
        """)

    crypto_cmake = textwrap.dedent("""
        function(crypto_message MESSAGE_OUTPUT)
            message("CRYPTO MESSAGE:${ARGV${0}}")
        endfunction()
        """)
    root_cmake = textwrap.dedent("""
        function(root_message MESSAGE_OUTPUT)
            message("ROOT MESSAGE:${ARGV${0}}")
        endfunction()
        """)
    client.save({"conanfile.py": conanfile,
                 "crypto.cmake": crypto_cmake,
                 "root.cmake": root_cmake})
    client.run("create .")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = ["CMakeLists.txt"]
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "openssl/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()

            def package_info(self):
                self.cpp_info.requires = ["openssl::crypto"]
        """)

    cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            find_package(openssl CONFIG)
            crypto_message("hello!")
            root_message("hello!")
            """)
    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    # As we are requiring only "crypto" but it doesn't matter, it is not possible to include
    # only crypto build_modules
    client.run("create .", assert_error=True)
    assert 'Unknown CMake command "crypto_message"' in client.out

    # Comment the function call
    client.save({"CMakeLists.txt": cmakelists.replace("crypto", "#crypto")})
    assert "ROOT MESSAGE:hello!" not in client.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("editable", [True, False])
def test_build_modules_custom_script_editable(editable):
    c = TestClient()
    conanfile = textwrap.dedent(r"""
        import os, glob
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        from conan.tools.files import copy, save

        class Conan(ConanFile):
            name = "myfunctions"
            version = "1.0"
            exports_sources = ["src/*.cmake"]
            settings = "build_type", "arch"

            def build(self):
                cmake = 'set(MY_CMAKE_PATH ${CMAKE_CURRENT_LIST_DIR})\n'\
                        'macro(otherfunc)\n'\
                        'file(READ "${MY_CMAKE_PATH}/my.txt" c)\n'\
                        'message("Hello ${c}!!!!")\nendmacro()'
                save(self, "otherfuncs.cmake", cmake)
                save(self, "my.txt", "contents of text file!!!!")

            def layout(self):
                cmake_layout(self, src_folder="src")
                src = glob.glob(os.path.join(self.recipe_folder, self.folders.source, "*.cmake"))
                build = glob.glob(os.path.join(self.recipe_folder, self.folders.build, "*.cmake"))
                self.cpp.source.set_property("cmake_build_modules", src)
                self.cpp.build.set_property("cmake_build_modules", build)

            def package(self):
                copy(self, "*.cmake", self.source_folder, os.path.join(self.package_folder, "mods"),
                     keep_path=False)
                copy(self, "*.cmake", self.build_folder, os.path.join(self.package_folder, "mods"),
                     keep_path=False)
                copy(self, "*.txt", self.build_folder, os.path.join(self.package_folder, "mods"),
                     keep_path=False)

            def package_info(self):
                self.cpp_info.set_property("cmake_build_modules", glob.glob("mods/*.cmake"))
        """)

    myfunction = textwrap.dedent("""
        function(myfunction)
            message("Hello myfunction!!!!")
        endfunction()
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "CMakeDeps"
            requires = "myfunctions/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(test)
        find_package(myfunctions CONFIG REQUIRED)
        myfunction()
        otherfunc()
        """)
    c.save({"functions/conanfile.py": conanfile,
            "functions/src/myfunction.cmake": myfunction,
            "app/conanfile.py": consumer,
            "app/CMakeLists.txt": cmakelists})

    if editable:
        c.run("editable add functions")
        c.run('build functions -c tools.cmake.cmake_layout:build_folder_vars="[\'settings.arch\']"')
    else:
        c.run("create functions")
    c.run('build app -c tools.cmake.cmake_layout:build_folder_vars="[\'settings.arch\']"')
    assert "Hello myfunction!!!!" in c.out
    assert "Hello contents of text file!!!!" in c.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("editable", [True, False])
def test_build_modules_custom_script_editable_package(editable):
    # same as above, but with files from the package folder
    c = TestClient()
    conanfile = textwrap.dedent(r"""
        import os, glob
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        from conan.tools.files import copy, save

        class Conan(ConanFile):
            name = "myfunctions"
            version = "1.0"
            exports_sources = ["src/*.cmake", "src/vis/*.vis"]
            settings = "build_type", "arch"

            def build(self):
                config = str(self.settings.build_type).upper()
                cmake = f'set(MY_CMAKE_PATH ${{{self.name}_RES_DIRS_{config}}})\n'\
                        'macro(otherfunc)\n'\
                        'file(READ "${MY_CMAKE_PATH}/my.vis" c)\n'\
                        'message("Hello ${c}!!!!")\nendmacro()'
                save(self, "otherfuncs.cmake", cmake)

            def layout(self):
                cmake_layout(self, src_folder="src")
                src = glob.glob(os.path.join(self.recipe_folder, self.folders.source, "*.cmake"))
                build = glob.glob(os.path.join(self.recipe_folder, self.folders.build, "*.cmake"))
                self.cpp.source.set_property("cmake_build_modules", src)
                self.cpp.build.set_property("cmake_build_modules", build)
                self.cpp.source.resdirs = ["vis"]

            def package(self):
                copy(self, "*.cmake", self.source_folder, os.path.join(self.package_folder, "mods"),
                     keep_path=False)
                copy(self, "*.cmake", self.build_folder, os.path.join(self.package_folder, "mods"),
                     keep_path=False)
                copy(self, "*.vis", self.source_folder, os.path.join(self.package_folder, "mods"),
                     keep_path=False)

            def package_info(self):
                self.cpp_info.resdirs = ["mods"]
                self.cpp_info.set_property("cmake_build_modules", glob.glob("mods/*.cmake"))
        """)

    myfunction = textwrap.dedent("""
        function(myfunction)
            message("Hello myfunction!!!!")
        endfunction()
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "CMakeDeps"
            requires = "myfunctions/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(test)
        find_package(myfunctions CONFIG REQUIRED)
        myfunction()
        otherfunc()
        """)
    c.save({"functions/conanfile.py": conanfile,
            "functions/src/myfunction.cmake": myfunction,
            "functions/src/vis/my.vis": "contents of text file!!!!",
            "app/conanfile.py": consumer,
            "app/CMakeLists.txt": cmakelists})

    if editable:
        c.run("editable add functions")
        c.run('build functions -c tools.cmake.cmake_layout:build_folder_vars="[\'settings.arch\']"')
    else:
        c.run("create functions -vv")
    c.run('build app -c tools.cmake.cmake_layout:build_folder_vars="[\'settings.arch\']"')
    assert "Hello myfunction!!!!" in c.out
    assert "Hello contents of text file!!!!" in c.out
