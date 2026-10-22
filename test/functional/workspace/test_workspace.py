import os
import platform
import shutil
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import TestClient
from conan.tools.files import replace_in_file


@pytest.mark.tool("cmake")
def test_build():
    # This is not using the meta-project at all
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace build")
    assert "conanfile.py (app1/0.1): Calling build()" in c.out
    assert "conanfile.py (app1/0.1): Running CMake.build()" in c.out
    # it works without failing


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_metabuild():
    # This is using the meta-project
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace super-install")
    assert os.path.exists(os.path.join(c.current_folder, "CMakeUserPresets.json"))
    build_folder = "build/Release" if platform.system() != "Windows" else "build"
    assert os.path.exists(os.path.join(c.current_folder, build_folder, "generators"))
    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")
    assert "Conan: Target declared 'mymath::mymath'" in c.out
    assert "Adding project: liba" in c.out
    assert "Adding project: libb" in c.out
    assert "Adding project: app1" in c.out
    c.run_command("cmake --build --preset conan-release")
    # it doesn't fail


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_new_template_and_different_folder():
    """
    Issue related: https://github.com/conan-io/conan/issues/18813
    """
    c = TestClient()
    c.run("new workspace")
    shutil.move(os.path.join(c.current_folder, "liba"), os.path.join(c.current_folder, "libX"))
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "conanws.yml"),
                    "  - path: liba",
                    "  - path: libX")
    c.run("workspace super-install")
    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")  # it does not fail
    assert "Adding project: liba" in c.out
    assert "Adding project: libb" in c.out
    assert "Adding project: app1" in c.out


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_super_build_different_layouts():
    """
    https://github.com/conan-io/conan/issues/18875
    """
    c = TestClient()
    c.run("new workspace")
    liba_src = os.path.join(c.current_folder, "liba", "mysrc")
    os.makedirs(liba_src)
    shutil.move(os.path.join(c.current_folder, "liba", "CMakeLists.txt"), liba_src)
    shutil.move(os.path.join(c.current_folder, "liba", "include"), liba_src,)
    shutil.move(os.path.join(c.current_folder, "liba", "src"), liba_src)
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "liba", "conanfile.py"),
                    "cmake_layout(self)",
                    "cmake_layout(self, src_folder='mysrc')")

    c.run("workspace super-install")

    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")  # it does not fail
    assert "Adding project: liba" in c.out
    assert "Adding project: libb" in c.out
    assert "Adding project: app1" in c.out


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_super_build_private_version_ambiguous():
    """
    https://github.com/conan-io/conan/issues/20304
    Known, accepted trade-off (not a bug to fix): "core" and "other" are two
    unrelated editables, each with its own *private* (visible=False) dependency on a
    different version of "leaf". This proves, at the real CMake/find_package level
    (not just by inspecting Conan-generated file content), what test_workspace.py's
    test_link_libraries_editable_private_version_ambiguous shows at the graph level:
    the monolithic build's top-level CMakeLists.txt pulls "core" and "other" in as
    source via the same FetchContent_Declare(..., OVERRIDE_FIND_PACKAGE) mechanism
    "conan new workspace" scaffolds (see "Adding project" below), but "leaf" itself is
    a regular, non-editable dependency resolved via a single, shared, generated
    find_package() config - there is only one CMAKE_PREFIX_PATH for the whole
    monolithic build. So both "core" and "other" end up calling find_package(leaf)
    from their own CMakeLists.txt and get back the exact same version, even though
    they each declared a different one.
    """
    c = TestClient()
    workspace = textwrap.dedent("""
        from conan import ConanFile, Workspace
        from conan.tools.cmake import CMakeConfigDeps, CMakeToolchain, cmake_layout
        from conan.tools.files import save


        class MyWs(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def generate(self):
                CMakeConfigDeps(self).generate()
                CMakeToolchain(self).generate()

            def layout(self):
                cmake_layout(self)


        class MyWorkspace(Workspace):
            def root_conanfile(self):
                return MyWs

            def packages(self):
                return [{"path": "core", "ref": "core/1.0"},
                        {"path": "other", "ref": "other/1.0"}]

            def build_order(self, order):
                super().build_order(order)
                pkglist = " ".join([f'{it["ref"].name}:{it["folder"]}'
                                    for level in order for it in level])
                save(self, "build/conanws_build_order.cmake",
                    f"set(CONAN_WS_BUILD_ORDER {pkglist})")
        """)
    # Same FetchContent_Declare(..., OVERRIDE_FIND_PACKAGE) loop that "conan new
    # workspace" scaffolds: it is how a real monolithic build brings editable sources
    # into one shared CMake project.
    root_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.25)
        project(monorepo CXX)

        include(FetchContent)

        function(add_project PACKAGE_NAME SUBFOLDER)
            message(STATUS "Adding project: ${PACKAGE_NAME}. Folder: ${SUBFOLDER}")
            FetchContent_Declare(
                ${PACKAGE_NAME}
                SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/${SUBFOLDER}
                SYSTEM
                OVERRIDE_FIND_PACKAGE
            )
            FetchContent_MakeAvailable(${PACKAGE_NAME})
        endfunction()

        include(build/conanws_build_order.cmake)

        foreach(pair ${CONAN_WS_BUILD_ORDER})
            string(FIND "${pair}" ":" pos)
            string(SUBSTRING "${pair}" 0 "${pos}" pkg)
            math(EXPR pos "${pos} + 1")  # Skip the separator
            string(SUBSTRING "${pair}" "${pos}" -1 folder)

            add_project(${pkg} ${folder})
            get_target_property(target_type ${pkg} TYPE)
            if (NOT target_type STREQUAL "EXECUTABLE")
                add_library(${pkg}::${pkg} ALIAS ${pkg})
            endif()
        endforeach()
        """)

    def pkg_cmake(name):
        # Each editable independently does its own find_package(leaf) and reports
        # what it got, so the mismatch is visible directly in the cmake configure log.
        return textwrap.dedent(f"""\
            cmake_minimum_required(VERSION 3.25)
            project({name} CXX)

            find_package(leaf REQUIRED)
            message(STATUS "{name.upper()} sees leaf version: ${{leaf_VERSION_STRING}}")

            add_library({name} INTERFACE)
            target_link_libraries({name} INTERFACE leaf::leaf)
            """)

    def pkg_conanfile(name, leaf_version):
        return textwrap.dedent(f"""\
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout


            class Pkg(ConanFile):
                name = "{name}"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "CMakeLists.txt"

                def layout(self):
                    cmake_layout(self)

                def requirements(self):
                    self.requires("leaf/{leaf_version}", visible=False)
            """)

    c.save({"leaf/conanfile.py": GenConanfile("leaf"),
            "core/conanfile.py": pkg_conanfile("core", "1.0"),
            "core/CMakeLists.txt": pkg_cmake("core"),
            "other/conanfile.py": pkg_conanfile("other", "2.0"),
            "other/CMakeLists.txt": pkg_cmake("other"),
            "conanws.py": workspace,
            "CMakeLists.txt": root_cmake})
    c.run("create leaf --version=1.0")
    c.run("create leaf --version=2.0")
    c.run("workspace super-install")

    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}")
    # Both editables are genuinely pulled in as source via FetchContent
    assert "Adding project: core" in c.out
    assert "Adding project: other" in c.out

    # "core" declared leaf/1.0 and "other" declared leaf/2.0, but there is only one
    # find_package(leaf) resolution for the whole monolithic build: both report the
    # same (wrong, for one of them) version.
    assert "CORE sees leaf version: 2.0" in c.out
    assert "OTHER sees leaf version: 2.0" in c.out


# The workspace CMake needs at least 3.25 for find_package to work
@pytest.mark.tool("cmake", "3.27")
def test_super_build_two_editables_same_name():
    """
    https://github.com/conan-io/conan/issues/20304
    Unlike test_super_build_private_version_ambiguous above (silent wrong version, no
    warning), having TWO editables share the same name is not silently resolved: it
    crashes. A plain "workspace super-install" fails immediately ("Duplicated
    requirement") before reaching any of this, because every editable is a top-level
    requirement by default - see test_two_editables_same_name_different_version in
    test/integration/workspace/test_workspace.py. But that guard is incidental: using
    --pkg to select only "core" and "other" as top-level requirements sidesteps it, and
    Conan then accepts both editable "leaf/1.0" and "leaf/2.0" (reached only
    transitively, through "core"'s and "other"'s own private requirements) silently,
    side by side in the graph. The failure only shows up once the "conan new
    workspace"-style FetchContent build order tries to add BOTH "leaf" editables (from
    two different folders) as source into the one monolithic CMake project: the second
    one crashes CMake outright, with an error that says nothing about Conan,
    workspaces, or the actual duplicate-name root cause.
    """
    c = TestClient()
    workspace = textwrap.dedent("""
        from conan import ConanFile, Workspace
        from conan.tools.cmake import CMakeConfigDeps, CMakeToolchain, cmake_layout
        from conan.tools.files import save


        class MyWs(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def generate(self):
                CMakeConfigDeps(self).generate()
                CMakeToolchain(self).generate()

            def layout(self):
                cmake_layout(self)


        class MyWorkspace(Workspace):
            def root_conanfile(self):
                return MyWs

            def packages(self):
                return [{"path": "leaf_v1", "ref": "leaf/1.0"},
                        {"path": "leaf_v2", "ref": "leaf/2.0"},
                        {"path": "core", "ref": "core/1.0"},
                        {"path": "other", "ref": "other/1.0"}]

            def build_order(self, order):
                super().build_order(order)
                pkglist = " ".join([f'{it["ref"].name}:{it["folder"]}'
                                    for level in order for it in level])
                save(self, "build/conanws_build_order.cmake",
                    f"set(CONAN_WS_BUILD_ORDER {pkglist})")
        """)
    # Same FetchContent_Declare(..., OVERRIDE_FIND_PACKAGE) loop "conan new workspace"
    # scaffolds - see test_super_build_private_version_ambiguous above.
    root_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.25)
        project(monorepo CXX)

        include(FetchContent)

        function(add_project PACKAGE_NAME SUBFOLDER)
            message(STATUS "Adding project: ${PACKAGE_NAME}. Folder: ${SUBFOLDER}")
            FetchContent_Declare(
                ${PACKAGE_NAME}
                SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/${SUBFOLDER}
                SYSTEM
                OVERRIDE_FIND_PACKAGE
            )
            FetchContent_MakeAvailable(${PACKAGE_NAME})
        endfunction()

        include(build/conanws_build_order.cmake)

        foreach(pair ${CONAN_WS_BUILD_ORDER})
            string(FIND "${pair}" ":" pos)
            string(SUBSTRING "${pair}" 0 "${pos}" pkg)
            math(EXPR pos "${pos} + 1")  # Skip the separator
            string(SUBSTRING "${pair}" "${pos}" -1 folder)

            add_project(${pkg} ${folder})
            get_target_property(target_type ${pkg} TYPE)
            if (NOT target_type STREQUAL "EXECUTABLE")
                add_library(${pkg}::${pkg} ALIAS ${pkg})
            endif()
        endforeach()
        """)
    leaf_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.25)
        project(leaf CXX)

        add_library(leaf INTERFACE)
        """)

    def pkg_cmake(name):
        return textwrap.dedent(f"""\
            cmake_minimum_required(VERSION 3.25)
            project({name} CXX)

            find_package(leaf REQUIRED)

            add_library({name} INTERFACE)
            target_link_libraries({name} INTERFACE leaf::leaf)
            """)

    def pkg_conanfile(name, leaf_version):
        return textwrap.dedent(f"""\
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout


            class Pkg(ConanFile):
                name = "{name}"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "CMakeLists.txt"

                def layout(self):
                    cmake_layout(self)

                def requirements(self):
                    self.requires("leaf/{leaf_version}", visible=False)
            """)

    c.save({"leaf_v1/conanfile.py": GenConanfile("leaf", "1.0"),
            "leaf_v1/CMakeLists.txt": leaf_cmake,
            "leaf_v2/conanfile.py": GenConanfile("leaf", "2.0"),
            "leaf_v2/CMakeLists.txt": leaf_cmake,
            "core/conanfile.py": pkg_conanfile("core", "1.0"),
            "core/CMakeLists.txt": pkg_cmake("core"),
            "other/conanfile.py": pkg_conanfile("other", "2.0"),
            "other/CMakeLists.txt": pkg_cmake("other"),
            "conanws.py": workspace,
            "CMakeLists.txt": root_cmake})
    # --pkg selects only "core"/"other" as top-level requirements, sidestepping the
    # "Duplicated requirement" guard a plain "workspace super-install" would hit
    # immediately (both "leaf" editables are still reached transitively and end up in
    # the build order regardless).
    c.run("workspace super-install --pkg=core/1.0 --pkg=other/1.0")

    config_preset = "conan-default" if platform.system() == "Windows" else "conan-release"
    c.run_command(f"cmake --preset {config_preset}", assert_error=True)
    assert "Adding project: leaf. Folder: leaf_v1" in c.out
    assert "Adding project: leaf. Folder: leaf_v2" in c.out
    # CMake wraps this message at a column that can vary, so check the two halves
    # separately rather than one exact substring.
    assert 'add_library cannot create ALIAS target "leaf::leaf" because another' in c.out
    assert "the same name already exists" in c.out
