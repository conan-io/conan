import re
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_cmakedeps_direct_deps_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "lib"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["myincludes"]
                self.cpp_info.libdirs = ["mylib"]
                self.cpp_info.frameworkdirs = ["myframework"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "lib/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeConfigDeps"
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install .")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert "set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)" in cmake_paths
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/bin\"", cmake_paths)  # default
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/mylib\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/myincludes\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_FRAMEWORK_PATH \".*/myframework\"", cmake_paths)


def test_cmakedeps_transitive_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "liba"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["includea"]
                self.cpp_info.libdirs = ["liba"]
                self.cpp_info.bindirs = ["bina"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "libb"
            version = "1.0"
            requires = "liba/1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["includeb"]
                self.cpp_info.libdirs = ["libb"]
                self.cpp_info.bindirs = ["binb"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class PkgConan(ConanFile):
            requires = "libb/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeConfigDeps"
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install .")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/libb.*/p/binb\"\)", cmake_paths)
    assert not re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH /bina\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/libb.*/p/libb\" \".*/liba.*/p/liba\"\)",
                     cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/libb.*/p/includeb\" "
                     r"\".*/liba.*/p/includea\"\)", cmake_paths)


def test_cmakedeps_deployer_relative_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "liba"
            version = "1.0"

            def package_info(self):
                self.cpp_info.includedirs = ["includea"]
                self.cpp_info.libdirs = ["bina"]
                self.cpp_info.bindirs = ["bina"]
                crypto_module = os.path.join("share", "cmake", "crypto.cmake")
                self.cpp_info.set_property("cmake_build_modules", [crypto_module])
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    conanfile_cmake = textwrap.dedent("""
        import os
        from conan.tools.files import save
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "libb"
            version = "1.0"

            def package(self):
                save(self, os.path.join(self.package_folder, "libb-config.cmake"), "")
            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "none")
        """)

    c.save({"conanfile.py": conanfile_cmake})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "liba/1.0", "libb/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeConfigDeps"
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)

    # Now with a deployment
    c.run(f"install . --deployer=full_deploy")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert 'set(libb_DIR "${CMAKE_CURRENT_LIST_DIR}/full_deploy/host/libb/1.0")' in cmake_paths
    assert ('set(CONAN_RUNTIME_LIB_DIRS "$<$<CONFIG:Release>:${CMAKE_CURRENT_LIST_DIR}'
            '/full_deploy/host/liba/1.0/bina>"') in cmake_paths
    liba_config = c.load("liba-config.cmake")
    assert ('include("${CMAKE_CURRENT_LIST_DIR}/full_deploy/'
            'host/liba/1.0/share/cmake/crypto.cmake")') in liba_config
    assert ('set(liba_INCLUDE_DIRS "${CMAKE_CURRENT_LIST_DIR}/full_deploy/'
            'host/liba/1.0/includea" )') in liba_config
    liba_targets = c.load("liba-Targets-release.cmake")
    assert ('set(liba_PACKAGE_FOLDER_RELEASE "${CMAKE_CURRENT_LIST_DIR}/full_deploy/'
            'host/liba/1.0")') in liba_targets


def test_cmakeconfigdeps_recipe():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan.tools.cmake import CMakeConfigDeps
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "build_type"
            requires = "dep/0.1"
            def generate(self):
                deps = CMakeConfigDeps(self)
                deps.generate()
    """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "app/conanfile.py": conanfile})
    c.run("create dep")
    c.run("install app")
    assert "WARN: experimental: CMakeConfigDeps is experimental" in c.out

    # attribute generator
    conanfile = textwrap.dedent("""
        from conan.tools.cmake import CMakeConfigDeps
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "build_type"
            requires = "dep/0.1"
            generators = "CMakeConfigDeps"
        """)
    c.save({"app/conanfile.py": conanfile}, clean_first=True)
    c.run("install app")
    assert "WARN: experimental: CMakeConfigDeps is experimental" in c.out

    # conanfile.txt
    conanfile = textwrap.dedent("""
        [requires]
        dep/0.1
        [generators]
        CMakeConfigDeps
        """)
    c.save({"app/conanfile.txt": conanfile}, clean_first=True)
    c.run("install app")
    assert "WARN: experimental: CMakeConfigDeps is experimental" in c.out


def test_system_wrappers():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "lib"
            version = "system"
            package_type = "shared-library"

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libdirs = []
                self.cpp_info.system_libs = ["my_system_cool_lib"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    c.run(f"install --requires=lib/system -g CMakeConfigDeps")
    cmake = c.load("lib-Targets-release.cmake")
    assert "add_library(lib::lib INTERFACE IMPORTED)" in cmake
    assert "set_property(TARGET lib::lib APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
           '             $<$<CONFIG:RELEASE>:my_system_cool_lib>)' in cmake


def test_autolink_pragma():
    """https://github.com/conan-io/conan/issues/10837"""
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.set_property("cmake_set_interface_link_directories", True)
        """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": GenConanfile().with_test("pass")
                                                       .with_settings("build_type")
                                                       .with_generator("CMakeConfigDeps")})
    c.run("create . --name=pkg --version=0.1")
    assert "CMakeConfigDeps: cmake_set_interface_link_directories deprecated" in c.out
    c.run(f"create . --name=pkg --version=0.1")
    assert "CMakeConfigDeps: cmake_set_interface_link_directories deprecated and invalid. " \
           "The package 'package_info()' must correctly define the (CPS) information" in c.out


def test_consuming_cpp_info_with_components_dependency_from_same_package():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.components["lib"].type = 'shared-library'
                self.cpp_info.components["lib_extended"].type = 'shared-library'
                self.cpp_info.components["lib_extended"].requires = ['lib']
        """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                       .with_test("pass")
                                                       .with_generator("CMakeConfigDeps")})
    c.run(f"create . --name=pkg --version=0.1")
    # it doesn't break
    assert "find_package(pkg)" in c.out


def test_consuming_cpp_info_with_components_dependency_from_other_package():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                self.cpp_info.components["lib"].type = 'shared-library'
    """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/0.1"
            def package_info(self):
                self.cpp_info.components["lib"].type = 'shared-library'
                self.cpp_info.components["lib"].requires = ['dep::lib']
        """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": conanfile,
            "pkg/test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                           .with_test("pass")
                                                           .with_generator("CMakeConfigDeps")})
    c.run("create dep")
    c.run(f"create pkg --name=pkg --version=0.1")
    # it doesn't break
    assert "find_package(pkg)" in c.out


def test_error_incorrect_component():
    # https://github.com/conan-io/conan/issues/18554
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/0.1"
            def package_info(self):
                self.cpp_info.requires = ['dep::lib']
        """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": conanfile,
            "pkg/test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                           .with_generator("CMakeConfigDeps")
                                                           .with_test("pass")})
    c.run("create dep")
    c.run(f"create pkg --name=pkg --version=0.1", assert_error=True)
    assert ("ERROR: Error in generator 'CMakeConfigDeps': pkg/0.1 recipe cpp_info did .requires to "
            "'dep::lib' but component 'lib' not found in dep") in c.out


def test_consuming_cpp_info_transitively_by_requiring_root_component():
    c = TestClient()
    dependent_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Dependent(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            name = 'dependent'
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def requirements(self):
                self.requires('dependent/0.1')
            def package_info(self):
                self.cpp_info.type = 'shared-library'
                self.cpp_info.requires = ['dependent::dependent']
        """)
    test_package = textwrap.dedent("""
        from conan import ConanFile
        class TestPkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "VirtualRunEnv", "CMakeConfigDeps"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
        """)
    c.save({"dependent/conanfile.py": dependent_conanfile,
            "main/conanfile.py": conanfile,
            "main/test_package/conanfile.py": test_package})
    c.run("create ./dependent/ --name=dependent --version=0.1")
    c.run(f"create ./main/ --name=pkg --version=0.1")


def test_cmake_find_mode_deprecated():
    tc = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                # Having both is ok as the user expects that config would
                # be generated nonetheless
                self.cpp_info.set_property("cmake_find_mode", "module")
        """)
    tc.save({"conanfile.py": dep})
    tc.run("create .")
    tc.run(f"install --requires=dep/0.1 -g CMakeConfigDeps")
    assert "CMakeConfigDeps does not support module find mode"


def test_build_context_deprecated():
    tc = TestClient()
    conanfile = textwrap.dedent("""
           from conan.tools.cmake import CMakeConfigDeps
           from conan import ConanFile
           class TestConan(ConanFile):
               settings = "build_type"
               def generate(self):
                   deps = CMakeConfigDeps(self)
                   deps.build_context_activated = ["bar"]
                   deps.build_context_suffix = {"bar": "_BUILD"}
                   deps.build_context_build_modules = ["myfunctions"]
                   deps.check_components_exist = True
                   deps.generate()
       """)
    tc.save({"conanfile.py": conanfile})
    tc.run("install .")
    assert "WARN: deprecated: CMakeConfigDeps.build_context_activated is deprecated" in tc.out
    assert "WARN: deprecated: CMakeConfigDeps.build_context_suffix is deprecated" in tc.out
    assert "WARN: deprecated: CMakeConfigDeps.build_context_build_modules is deprecated" in tc.out
    assert "WARN: deprecated: CMakeConfigDeps.check_components_exist is deprecated" in tc.out


def test_cmake_extra_dependencies():
    tc = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                self.cpp_info.set_property("cmake_extra_dependencies", ["MyOpenMPI"])
                self.cpp_info.set_property("cmake_extra_interface_libs", ["MyOpenMPILib"])
        """)
    tc.save({"conanfile.py": dep})
    tc.run("create .")
    tc.run(f"install --requires=dep/0.1 -g CMakeConfigDeps")
    dep = tc.load("dep-Targets-release.cmake")
    assert "find_dependency(MyOpenMPI REQUIRED )" in dep
    assert "set_property(TARGET dep::dep APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
           "             $<$<CONFIG:RELEASE>:MyOpenMPILib>)" in dep


def test_cmake_component_type_none_check():
    tc = TestClient()
    dep = (GenConanfile("dep", "0.1")
           .with_package_file("lib/libmain.so", "dynamic library")
           .with_package_info({"components": {"main": {"libs": ["libmain.so"], "type": "'shared-library'"}}}))
    tc.save({"conanfile.py": dep})
    tc.run("create")
    tc.run("install --requires=dep/0.1 -g CMakeConfigDeps")
    assert "None is not a valid PackageType" not in tc.out


def test_cmake_extra_dependencies_components():
    tc = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                self.cpp_info.set_property("cmake_extra_dependencies", ["MyOpenMPI"])
                self.cpp_info.components["mycomp"].set_property("cmake_extra_interface_libs",
                                                                ["MyOpenMPILib"])
                self.cpp_info.components["mycomp"].libs = ["mycomplib"]
                self.cpp_info.components["mycomp"].type = "static-library"
                self.cpp_info.components["mycomp"].location = "lib/mycomp.a"
        """)
    tc.save({"conanfile.py": dep})
    tc.run("create .")
    tc.run(f"install --requires=dep/0.1 -g CMakeConfigDeps")
    dep = tc.load("dep-Targets-release.cmake")
    assert "find_dependency(MyOpenMPI REQUIRED )" in dep
    assert "set_property(TARGET dep::mycomp APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
           "             $<$<CONFIG:RELEASE>:MyOpenMPILib>)" in dep


class TestRequiresToApp:
    def test_requires_to_application(self):
        c = TestClient()
        automake = GenConanfile("automake", "0.1").with_package_type("application")
        conanfile = (GenConanfile("libtool", "0.1").with_package_type("static-library")
                                                   .with_requirement("automake/0.1"))
        test_package = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake

            class TestPkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "CMakeConfigDeps", "CMakeToolchain"

                def requirements(self):
                    self.requires(self.tested_reference_str)

                def test(self):
                    pass
            """)

        c.save({"automake/conanfile.py": automake,
                "libtool/conanfile.py": conanfile,
                "libtool/test_package/conanfile.py": test_package})
        c.run("create automake")
        c.run(f"create libtool")
        targets = c.load("libtool/test_package/libtool-Targets-release.cmake")
        # The libtool shouldn't depend on the automake::automake target
        assert "automake::automake" not in targets

    def test_requires_to_application_component(self):
        c = TestClient()
        automake = textwrap.dedent("""
            from conan import ConanFile
            class Dependent(ConanFile):
                name = "automake"
                version = "0.1"
                package_type = "application"

                def package_info(self):
                    self.cpp_info.components["myapp"].exe = "myapp"
                    self.cpp_info.components["myapp"].location = "path/to/myapp"
                    self.cpp_info.components["mylibapp"].type = "header-library"
            """)

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "libtool"
                version = "0.1"
                package_type = "static-library"

                def requirements(self):
                    self.requires('automake/0.1')
                def package_info(self):
                    self.cpp_info.requires = ["automake::mylibapp"]
            """)

        c.save({"automake/conanfile.py": automake,
                "libtool/conanfile.py": conanfile})
        c.run("create automake")

        c.run("create libtool")
        c.run("install --requires=libtool/0.1 -g CMakeConfigDeps")
        targets = c.load("libtool-Targets-release.cmake")
        # The libtool shouldn't depend on the automake::automake target
        assert "automake::automake" not in targets
        assert "# Requirement libtool::libtool -> automake::mylibapp (Full link: True)" in targets
        assert "$<$<CONFIG:RELEASE>:automake::mylibapp>" in targets

    def test_requires_from_library_component(self):
        c = TestClient()
        automake = GenConanfile("automake", "0.1").with_package_type("application")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "libtool"
                version = "0.1"
                package_type = "static-library"

                def requirements(self):
                    self.requires('automake/0.1')
                def package_info(self):
                    self.cpp_info.components["mycomp"].requires = ["automake::automake"]
            """)

        c.save({"automake/conanfile.py": automake,
                "libtool/conanfile.py": conanfile})
        c.run("create automake")
        c.run("create libtool")
        c.run("install --requires=libtool/0.1 -g CMakeConfigDeps")
        targets = c.load("libtool-Targets-release.cmake")
        # The libtool shouldn't depend on the automake::automake target
        assert "automake::automake" not in targets

    def test_requires_from_library_component_to_app_component(self):
        c = TestClient()
        automake = textwrap.dedent("""
            from conan import ConanFile
            class Dependent(ConanFile):
                name = "automake"
                version = "0.1"

                def package_info(self):
                    self.cpp_info.components["myapp"].exe = "myapp"
                    self.cpp_info.components["myapp"].location = "path/to/myapp"
                    self.cpp_info.components["mylibapp"].type = "header-library"
            """)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "libtool"
                version = "0.1"
                package_type = "static-library"

                def requirements(self):
                    self.requires('automake/0.1')
                def package_info(self):
                    self.cpp_info.components["mycomp"].requires = ["automake::myapp"]
            """)

        c.save({"automake/conanfile.py": automake,
                "libtool/conanfile.py": conanfile})
        c.run("create automake")
        c.run("create libtool")
        c.run("install --requires=libtool/0.1 -g CMakeConfigDeps")
        targets = c.load("libtool-Targets-release.cmake")
        # The libtool shouldn't depend on the automake::automake target
        assert "automake::myapp" not in targets
        assert "automake::automake" not in targets


def test_alias_cmakedeps_set_property():
    tc = TestClient()
    tc.save({"dep/conanfile.py": textwrap.dedent("""

        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["mycomp"].set_property("cmake_target_name",
                                                                "dep::mycomponent")
        """),
             "conanfile.py": textwrap.dedent("""
             from conan import ConanFile
             from conan.tools.cmake import CMakeConfigDeps, CMake
             class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"

                requires = "dep/1.0"

                def generate(self):
                    deps = CMakeConfigDeps(self)
                    deps.set_property("dep", "cmake_target_aliases", ["alias", "dep::other_name"])
                    deps.set_property("dep::mycomp", "cmake_target_aliases",
                                      ["component_alias", "dep::my_aliased_component"])
                    deps.generate()
             """)})
    tc.run("create dep")
    tc.run(f"install .")
    targets_data = tc.load('dep-Targets-release.cmake')
    assert "add_library(dep::dep" in targets_data
    assert "add_library(alias" in targets_data
    assert "add_library(dep::other_name" in targets_data

    assert "add_library(component_alias" in targets_data
    assert "add_library(dep::my_aliased_component" in targets_data


def test_package_info_extra_variables():
    """ Test extra_variables property - This just shows that it works,
    there are tests for cmaketoolchain that check the actual behavior
    of parsing the variables"""
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def package_info(self):
                self.cpp_info.set_property("cmake_extra_variables", {"FOO": 42,
                                           "BAR": 42,
                                           "CMAKE_GENERATOR_INSTANCE":
                                                 "${GENERATOR_INSTANCE}/buildTools/",
                                           "CACHE_VAR_DEFAULT_DOC": {"value": "hello world",
                                                                     "cache": True, "type": "PATH"}})
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.run(f"install --requires=pkg/0.1 -g CMakeConfigDeps "
               """-c tools.cmake.cmaketoolchain:extra_variables="{'BAR': 9}" """)
    target = client.load("pkg-config.cmake")
    assert 'set(BAR' not in target
    assert 'set(CMAKE_GENERATOR_INSTANCE "${GENERATOR_INSTANCE}/buildTools/")' in target
    assert 'set(FOO 42)' in target
    assert 'set(CACHE_VAR_DEFAULT_DOC "hello world" CACHE PATH "CACHE_VAR_DEFAULT_DOC")' in target


def test_target_defines_only():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def package_info(self):
                self.cpp_info.components["base"].includedirs = []
                self.cpp_info.components["base"].defines = ["FOO=1"]
                self.cpp_info.components["comp"].includedirs = ["include"]
                self.cpp_info.components["comp"].requires = ["base"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.run(f"install --requires=pkg/0.1 -g CMakeConfigDeps")
    target = client.load("pkg-Targets-release.cmake")
    assert 'add_library(pkg::base INTERFACE IMPORTED)' in target
    assert "# Requirement pkg::comp -> pkg::base (Full link: True)" in target


class TestLinkFeatures:
    def test_link_info_global_cpp_info(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                self.cpp_info.set_property("cmake_link_feature", "MYFET")
        """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")

        dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            requires = "pkg/1.0"
        """)
        tc.save({"conanfile.py": dep})
        tc.run("create")
        tc.run("install --requires=dep/1.0 -g CMakeConfigDeps")
        # The requirement should propagate the link feature info
        target = tc.load("dep-Targets-release.cmake")
        assert "# Requirement dep::dep -> pkg::pkg (Full link: True)\n# Link feature: MYFET" in target

    def test_link_info_local_component_from_interface(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                self.cpp_info.components["compA"].set_property("cmake_link_feature", "MYFET")
        """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")
        tc.run("install --requires=pkg/1.0 -g CMakeConfigDeps")
        targets = tc.load("pkg-Targets-release.cmake")
        # The interface library created as a global target should have the requirement
        assert "# Requirement pkg::pkg -> pkg::compA (Full link: True)\n# Link feature: MYFET" in targets

    def test_link_info_local_component_to_component_require(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                self.cpp_info.components["compA"].set_property("cmake_link_feature", "MYFET")
                self.cpp_info.components["compB"].requires = ["compA"]
        """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")
        tc.run("install --requires=pkg/1.0 -g CMakeConfigDeps")
        targets = tc.load("pkg-Targets-release.cmake")
        # The component requirement should have the link feature info
        assert "# Requirement pkg::compB -> pkg::compA (Full link: True)\n# Link feature: MYFET" in targets

    def test_link_info_lib_to_component_require(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                self.cpp_info.components["compA"].set_property("cmake_link_feature", "MYFET")
        """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")

        dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            requires = "pkg/1.0"

            def package_info(self):
                self.cpp_info.requires = ["pkg::compA"]
        """)
        tc.save({"conanfile.py": dep})
        tc.run("create")
        tc.run("install --requires=dep/1.0 -g CMakeConfigDeps")
        targets = tc.load("dep-Targets-release.cmake")
        # The requirement should have the link feature info
        assert "# Requirement dep::dep -> pkg::compA (Full link: True)\n# Link feature: MYFET" in targets


class TestLegacyVariables:
    def test_legacy_defines(self):
        # We used not to populate this.
        # We do for backward compatibility with old check_symbol_exists and similar CMake code
        tc = TestClient()
        tc.save({"conanfile.py": GenConanfile("mypkg", "1.0")
                .with_package_info({"defines": ["MY_DEFINE", "MYVAR=1"]})})
        tc.run("create")
        tc.run("install --requires=mypkg/1.0 -g CMakeConfigDeps")
        mypkg_config = tc.load("mypkg-config.cmake")
        assert 'set(mypkg_DEFINITIONS "-DMY_DEFINE;-DMYVAR=1" )' in mypkg_config

    def test_legacy_defines_multiple_components(self):
        tc = TestClient()
        tc.save({"conanfile.py": GenConanfile("mypkg", "1.0")
                 .with_package_info({"components": {"mypkg": {"defines": ["MY_DEFINE", "MYVAR=1"]},
                                                    "lib2": {"defines": ["MY_DEFINE2", "MYVAR2=1"]}}})
                 })
        tc.run("create")
        tc.run("install --requires=mypkg/1.0 -g CMakeConfigDeps")
        mypkg_config = tc.load("mypkg-config.cmake")
        assert 'set(mypkg_DEFINITIONS "-DMY_DEFINE2;-DMYVAR2=1;-DMY_DEFINE;-DMYVAR=1" )' in mypkg_config

    def test_legacy_libraries(self):
        tc = TestClient()
        tc.save({"conanfile.py": GenConanfile("mypkg", "1.0")
                 .with_package_file("lib/mylib1.a", "library")
                 .with_package_file("lib/mylib2.a", "library")
                 .with_package_info({"components": {"mypkg": {"libs": ["mylib1"]},
                                                    "lib2": {"libs": ["mylib2"]}}})
                 })
        tc.run("create")
        tc.run("install --requires=mypkg/1.0 -g CMakeConfigDeps")
        mypkg_config = tc.load("mypkg-config.cmake")
        # If there's no interface global target
        # mypkg::lib2 is not added to the list of libraries
        assert "set(mypkg_LIBRARIES mypkg::mypkg mypkg::lib2 )" in mypkg_config


class TestPropertiesBuildContext:
    def test_property_build_context(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeConfigDeps

            class PackageConan(ConanFile):
                name = "package"
                settings = "os", "arch", "compiler", "build_type"

                def requirements(self):
                    self.requires("zlib/1.3.1")

                def generate(self):
                    deps = CMakeConfigDeps(self)
                    deps.set_property("zlib", "cmake_file_name", "MyZlibName")
                    deps.generate()
            """)
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.3.1"),
                "pkg/conanfile.py": conanfile})
        c.run("create zlib")
        c.run("install pkg --build-require")
        assert "find_package(MyZlibName)" in c.out
        config = c.load("pkg/MyZlibNameConfig.cmake")
        assert 'set(MyZlibName_VERSION_STRING "1.3.1")' in config


class TestExtraFindExtraVariants:
    def test_generated_dir_entries(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
                from conan import ConanFile

                class HelloConan(ConanFile):
                    name = "hello"
                    version = "1.0"

                    def package_info(self):
                        self.cpp_info.set_property("cmake_file_name_variants", ["HellO", "HELLO"])
                """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")
        tc.run("install --requires=hello/1.0 -g CMakeConfigDeps")
        paths_content = tc.load("conan_cmakedeps_paths.cmake")
        assert "set(hello_DIR" in paths_content
        assert "set(HellO_DIR" in paths_content
        assert "set(HELLO_DIR" in paths_content

    def test_differing_names_instead_of_case(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "1.0"

            def package_info(self):
                self.cpp_info.set_property("cmake_file_name_variants", ["Bye!"])
        """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")
        tc.run("install --requires=hello/1.0 -g CMakeConfigDeps", assert_error=True)
        assert ("'cmake_file_name_variants' property contains "
                "entries that differ from the default 'cmake_file_name'='hello'") in tc.out

    def test_consumer_dependency_name_change(self):
        """ If the consumer changes the dependency name via
        cmake_file_name, the extra casings do not get generated"""
        tc = TestClient()
        hello = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "1.0"

            def package_info(self):
                self.cpp_info.set_property("cmake_file_name_variants", ["HellO"])
        """)
        tc.save({"hello/conanfile.py": hello})
        tc.run("create hello")

        conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeConfigDeps

        class Consumer(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/1.0"
            def generate(self):
                deps = CMakeConfigDeps(self)
                deps.set_property("hello", "cmake_file_name", "greetings")
                deps.generate()
        """)

        tc.save({"conanfile.py": conanfile})
        tc.run("install")
        assert ("'cmake_file_name_variants' property contains names "
                "with different casings than the defined name 'greetings'") in tc.out
        paths_content = tc.load("conan_cmakedeps_paths.cmake")
        assert "set(greetings_DIR" in paths_content
        # But the old casing names are not generated, even if they were defined in the package
        # they would not work
        assert "set(HellO_DIR" not in paths_content
        # The original name is not created in any case either way, as expected when cmake_file_name is used
        assert "set(hello_DIR" not in paths_content

    def test_generated_dir_none_find_mode_multi_entries(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
                from conan import ConanFile

                class HelloConan(ConanFile):
                    name = "hello"
                    version = "1.0"
                    settings = "build_type"

                    def package_info(self):
                        self.cpp_info.set_property("cmake_find_mode", "none")
                        self.cpp_info.set_property("cmake_file_name_variants", ["HellO", "HELLO"])
                """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")
        tc.run("create -s=build_type=Debug")
        tc.run("install --requires=hello/1.0 -g CMakeConfigDeps")
        paths_content = tc.load("conan_cmakedeps_paths.cmake")
        assert "set(hello_DIR" not in paths_content
        assert "set(HellO_DIR" not in paths_content
        assert "set(HELLO_DIR" not in paths_content

        assert "list(APPEND CONAN_hello_DIR_MULTI" in paths_content
        assert "list(APPEND CONAN_HellO_DIR_MULTI" in paths_content
        assert "list(APPEND CONAN_HELLO_DIR_MULTI" in paths_content

        tc.run("install --requires=hello/1.0 -g CMakeConfigDeps -s=build_type=Debug")
        paths_content = tc.load("conan_cmakedeps_paths.cmake")
        # Reading already existing MULTI variables works
        assert paths_content.count("list(APPEND CONAN_hello_DIR_MULTI") == 2
        assert paths_content.count("list(APPEND CONAN_HellO_DIR_MULTI") == 2
        assert paths_content.count("list(APPEND CONAN_HELLO_DIR_MULTI") == 2

    def test_find_file_in_package(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save

            class HelloConan(ConanFile):
                name = "hello"
                version = "1.0"
                settings = "build_type"

                def package(self):
                    save(self, os.path.join(self.package_folder, "HellOConfig.cmake"), "")

                def package_info(self):
                    self.cpp_info.builddirs = ["."]
                    self.cpp_info.set_property("cmake_find_mode", "none")
                    self.cpp_info.set_property("cmake_file_name_variants", ["HellO", "HELLO"])
            """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create")
        tc.run("create -s=build_type=Debug")
        tc.run("install --requires=hello/1.0 -g CMakeConfigDeps")
        paths_content = tc.load("conan_cmakedeps_paths.cmake")
        assert "set(hello_DIR" in paths_content
        assert "set(HellO_DIR" in paths_content
        assert "set(HELLO_DIR" in paths_content


def test_requires_only_component_target_generation():
    tc = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                self.cpp_info.components["compA"].includedirs = ["include"]
                self.cpp_info.components["compB"].includedirs = []
                self.cpp_info.components["compB"].requires = ["compA"]
    """)
    tc.save({"conanfile.py": conanfile})
    tc.run("create .")
    tc.run("install --requires=pkg/1.0 -g CMakeConfigDeps")
    target = tc.load("pkg-Targets-release.cmake")
    # An otherwise empty component is generated as a target if it requires another component
    # to work as an interface target for the requirement
    # (For example, useful when a component aggregates optional components under it)
    assert "add_library(pkg::compB INTERFACE" in target
    assert "# Requirement pkg::compB -> pkg::compA (Full link: True)" in target
    # And even if it's INTERFACE, the globally generated target requires it as usual
    assert "# Requirement pkg::pkg -> pkg::compB (Full link: True)" in target
