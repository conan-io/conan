import json
import textwrap

import pytest

from conan.api.model import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("require, pattern, alternative, pkg", [
    # PATTERN VERSIONS
    # override all dependencies to "dep" to a specific version,user and channel)
    # TODO: This is a version override, is this really wanted?
    ("dep/1.3", "dep/*", "dep/1.1", "dep/1.1"),
    ("dep/[>=1.0 <2]", "dep/*", "dep/1.1", "dep/1.1"),
    # override all dependencies to "dep" to the same version with other user, remove channel)
    ("dep/1.3", "dep/*", "dep/*@system", "dep/1.3@system"),
    ("dep/[>=1.0 <2]", "dep/*", "dep/*@system", "dep/1.1@system"),
    # override all dependencies to "dep" to the same version with other user, same channel)
    ("dep/1.3@comp/stable", "dep/*@*/*", "dep/*@system/*", "dep/1.3@system/stable"),
    ("dep/[>=1.0 <2]@comp/stable", "dep/*@*/*", "dep/*@system/*", "dep/1.1@system/stable"),
    # EXACT VERSIONS
    # replace exact dependency version for one in the system
    ("dep/1.1", "dep/1.1", "dep/1.1@system", "dep/1.1@system"),
    ("dep/[>=1.0 <2]", "dep/1.1", "dep/1.1@system", "dep/1.1@system"),
    ("dep/[>=1.0 <2]@comp", "dep/1.1@*", "dep/1.1@*/stable", "dep/1.1@comp/stable"),
    ("dep/1.1@comp", "dep/1.1@*", "dep/1.1@*/stable", "dep/1.1@comp/stable"),
    # PACKAGE ALTERNATIVES (zlib->zlibng)
    ("dep/1.0", "dep/*", "depng/*", "depng/1.0"),
    ("dep/[>=1.0 <2]", "dep/*", "depng/*", "depng/1.1"),
    ("dep/[>=1.0 <2]", "dep/1.1", "depng/1.2", "depng/1.2"),
    # NON MATCHING
    ("dep/1.3", "dep/1.1", "dep/1.1@system", "dep/1.3"),
    ("dep/1.3", "dep/*@comp", "dep/*@system", "dep/1.3"),
    ("dep/[>=1.0 <2]", "dep/2.1", "dep/2.1@system", "dep/1.1"),
    # PATTERN - PATTERN REPLACE
    ("dep/[>=1.3 <2]", "dep/*", "dep/[>=1.0 <1.9]", "dep/1.1"),
    # DIRECT REPLACE OF PINNED VERSIONS
    ("dep/1.3", "dep/1.3", "dep/1.5", "dep/1.5"),
])
@pytest.mark.parametrize("tool_require", [False, True])
class TestReplaceRequires:
    def test_alternative(self, tool_require, require, pattern, alternative, pkg):
        c = TestClient(light=True)
        conanfile = GenConanfile().with_tool_requires(require) if tool_require else \
            GenConanfile().with_requires(require)
        profile_tag = "replace_requires" if not tool_require else "replace_tool_requires"
        c.save({"dep/conanfile.py": GenConanfile(),
                "pkg/conanfile.py": conanfile,
                "profile": f"[{profile_tag}]\n{pattern}: {alternative}"})
        ref = RecipeReference.loads(pkg)
        user = f"--user={ref.user}" if ref.user else ""
        channel = f"--channel={ref.channel}" if ref.channel else ""
        c.run(f"create dep --name={ref.name} --version={ref.version} {user} {channel}")
        rrev = c.exported_recipe_revision()
        c.run("profile show -pr=profile")
        assert profile_tag in c.out
        c.run("install pkg -pr=profile")
        assert profile_tag in c.out
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)

        # Check lockfile
        c.run("lock create pkg -pr=profile")
        lock = c.load("pkg/conan.lock")
        assert f"{pkg}#{rrev}" in lock

        # c.run("create dep2 --version=1.2")
        # with lockfile
        c.run("install pkg -pr=profile")
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)

    def test_diamond(self, tool_require, require, pattern, alternative, pkg):
        c = TestClient(light=True)
        conanfile = GenConanfile().with_tool_requires(require) if tool_require else \
            GenConanfile().with_requires(require)
        profile_tag = "replace_requires" if not tool_require else "replace_tool_requires"

        c.save({"dep/conanfile.py": GenConanfile(),
                "libb/conanfile.py": conanfile,
                "libc/conanfile.py": conanfile,
                "app/conanfile.py": GenConanfile().with_requires("libb/0.1", "libc/0.1"),
                "profile": f"[{profile_tag}]\n{pattern}: {alternative}"})
        ref = RecipeReference.loads(pkg)
        user = f"--user={ref.user}" if ref.user else ""
        channel = f"--channel={ref.channel}" if ref.channel else ""
        c.run(f"create dep --name={ref.name} --version={ref.version} {user} {channel}")
        rrev = c.exported_recipe_revision()

        c.run("export libb --name=libb --version=0.1")
        c.run("export libc --name=libc --version=0.1")

        c.run("install app -pr=profile", assert_error=True)
        assert "ERROR: Missing binary: libb/0.1" in c.out
        assert "ERROR: Missing binary: libc/0.1" in c.out

        c.run("install app -pr=profile --build=missing")
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)

        # Check lockfile
        c.run("lock create app -pr=profile")
        lock = c.load("app/conan.lock")
        assert f"{pkg}#{rrev}" in lock

        # with lockfile
        c.run("install app -pr=profile")
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)


@pytest.mark.parametrize("pattern, replace", [
    ("pkg", "pkg/0.1"),
    ("pkg/*", "pkg"),
    ("pkg/*:pid1", "pkg/0.1"),
    ("pkg/*:pid1", "pkg/0.1:pid2"),
    ("pkg/*", "pkg/0.1:pid2"),
    (":", ""),
    ("pkg/version:pid", ""),
    ("pkg/version:pid", ":")
])
def test_replace_requires_errors(pattern, replace):
    c = TestClient(light=True)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "app/conanfile.py": GenConanfile().with_requires("pkg/0.2"),
            "profile": f"[replace_requires]\n{pattern}: {replace}"})
    c.run("create pkg")
    c.run("install app -pr=profile", assert_error=True)
    assert "ERROR: Error reading 'profile' profile: Error in [replace_xxx]" in c.out


def test_replace_requires_invalid_requires_errors():
    """
    replacing for something incorrect not existing is not an error per-se, it is valid that
    a recipe requires("pkg/2.*"), and then it will fail because such package doesn't exist
    """
    c = TestClient(light=True)
    c.save({"app/conanfile.py": GenConanfile().with_requires("pkg/0.2"),
            "profile": f"[replace_requires]\npkg/0.2: pkg/2.*"})
    c.run("install app -pr=profile", assert_error=True)
    assert "pkg/0.2: pkg/2.*" in c.out  # The replacement happens
    assert "ERROR: Package 'pkg/2.*' not resolved" in c.out


def test_replace_requires_json_format():
    c = TestClient(light=True)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.2"),
            "app/conanfile.py": GenConanfile().with_requires("pkg/0.1"),
            "profile": f"[replace_requires]\npkg/0.1: pkg/0.2"})
    c.run("create pkg")
    c.run("install app -pr=profile --format=json")
    assert "pkg/0.1: pkg/0.2" in c.out  # The replacement happens
    graph = json.loads(c.stdout)
    assert graph["graph"]["replaced_requires"] == {"pkg/0.1": "pkg/0.2"}
    assert graph["graph"]["nodes"]["0"]["dependencies"]["1"]["ref"] == "pkg/0.2"
    assert graph["graph"]["nodes"]["0"]["dependencies"]["1"]["require"] == "pkg/0.1"


def test_replace_requires_test_requires():
    c = TestClient(light=True)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "0.2"),
            "app/conanfile.py": GenConanfile().with_test_requires("gtest/0.1"),
            "profile": f"[replace_requires]\ngtest/0.1: gtest/0.2"})
    c.run("create gtest")
    c.run("install app -pr=profile")
    assert "gtest/0.1: gtest/0.2" in c.out  # The replacement happens


# We test even replacing by itself, not great, but shouldn't crash
@pytest.mark.parametrize("name, version", [("zlib", "0.1"), ("zlib", "0.2"), ("zlib-ng", "0.1")])
def test_replace_requires_consumer_references(name, version):
    c = TestClient()
    # IMPORTANT: The replacement package must be target-compatible
    dep = textwrap.dedent(f"""
        from conan import ConanFile
        class ZlibNG(ConanFile):
            name = "{name}"
            version = "{version}"
            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "ZLIB")
                self.cpp_info.set_property("cmake_target_name", "ZLIB::ZLIB")
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class App(ConanFile):
            name = "app"
            version = "0.1"
            settings = "build_type"
            requires = "zlib/0.1"
            generators = "CMakeDeps"

            def generate(self):
                self.output.info(f"DEP ZLIB generate: {self.dependencies['zlib'].ref.name}!")
            def build(self):
                self.output.info(f"DEP ZLIB build: {self.dependencies['zlib'].ref.name}!")
            def package_info(self):
                self.output.info(f"DEP ZLIB package_info: {self.dependencies['zlib'].ref.name}!")
                self.cpp_info.requires = ["zlib::zlib"]
        """)
    c.save({"dep/conanfile.py": dep,
            "app/conanfile.py": conanfile,
            "profile": f"[replace_requires]\nzlib/0.1: {name}/{version}"})
    c.run("create dep")
    c.run("build app -pr=profile")
    assert f"zlib/0.1: {name}/{version}" in c.out
    assert f"DEP ZLIB generate: {name}!" in c.out
    assert f"conanfile.py (app/0.1): DEP ZLIB build: {name}!" in c.out
    # Check generated CMake code. If the targets are NOT compatible, then the replacement
    # Cannot happen
    assert "find_package(ZLIB)" in c.out
    assert "target_link_libraries(... ZLIB::ZLIB)" in c.out
    cmake = c.load("app/ZLIBTargets.cmake")
    assert "add_library(ZLIB::ZLIB INTERFACE IMPORTED)" in cmake
    c.run("create app -pr=profile")
    assert f"zlib/0.1: {name}/{version}" in c.out
    assert f"DEP ZLIB generate: {name}!" in c.out
    assert f"app/0.1: DEP ZLIB build: {name}!" in c.out
    if name == "zlib-ng":
        # CMakeDeps can not be used to consume replaced requires for different packages
        # only CMakeConfigDeps has this capability
        c.run("install --requires=app/0.1 -pr=profile -g CMakeDeps", assert_error=True)


def test_replace_requires_consumer_references_error_multiple():
    # https://github.com/conan-io/conan/issues/17407
    c = TestClient()
    # IMPORTANT: The replacement package must be target-compatible
    zlib = textwrap.dedent("""
        from conan import ConanFile
        class ZlibNG(ConanFile):
            name = "zlib"
            version = "0.2"
            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "ZLIB")
                self.cpp_info.set_property("cmake_target_name", "ZLIB::ZLIB")
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class App(ConanFile):
            name = "app"
            version = "0.1"
            settings = "build_type"
            requires = "zlib/0.1", "bzip2/0.1"
            generators = "CMakeDeps"

            def generate(self):
                self.output.info(f"DEP ZLIB generate: {self.dependencies['zlib'].ref.name}!")
                self.output.info(f"DEP BZIP2 generate: {self.dependencies['bzip2'].ref.name}!")
            def build(self):
                self.output.info(f"DEP ZLIB build: {self.dependencies['zlib'].ref.name}!")
                self.output.info(f"DEP BZIP2 build: {self.dependencies['bzip2'].ref.name}!")
            def package_info(self):
                self.output.info(f"DEP ZLIB package_info: {self.dependencies['zlib'].ref.name}!")
                self.cpp_info.requires = ["zlib::zlib", "bzip2::bzip2"]
        """)
    c.save({"zlib/conanfile.py": zlib,
            "app/conanfile.py": conanfile,
            "profile": "[replace_requires]\nzlib/0.1: zlib/0.2\nbzip2/0.1: zlib/0.2"})
    c.run("create zlib")
    c.run("build app -pr=profile")
    assert "zlib/0.1: zlib/0.2" in c.out
    assert "DEP ZLIB generate: zlib!" in c.out
    assert "conanfile.py (app/0.1): DEP ZLIB build: zlib!" in c.out
    assert "DEP BZIP2 generate: zlib!" in c.out
    assert "conanfile.py (app/0.1): DEP BZIP2 build: zlib!" in c.out
    # Check generated CMake code. If the targets are NOT compatible, then the replacement
    # Cannot happen
    assert "find_package(ZLIB)" in c.out
    assert "target_link_libraries(... ZLIB::ZLIB ZLIB::ZLIB)" in c.out
    cmake = c.load("app/ZLIBTargets.cmake")
    assert "add_library(ZLIB::ZLIB INTERFACE IMPORTED)" in cmake
    c.run("create app -pr=profile")
    assert "zlib/0.1: zlib/0.2" in c.out
    assert "DEP ZLIB generate: zlib!" in c.out
    assert "app/0.1: DEP ZLIB build: zlib!" in c.out


def test_replace_requires_consumer_components_options():
    c = TestClient()
    # IMPORTANT: The replacement package must be target-compatible
    zlib_ng = textwrap.dedent("""
        from conan import ConanFile
        class ZlibNG(ConanFile):
            name = "zlib-ng"
            version = "0.1"
            options = {"compat": [False, True]}
            default_options = {"compat": False}
            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "ZLIB")
                self.cpp_info.set_property("cmake_target_name", "ZLIB::ZLIB")
                if self.options.compat:
                    self.cpp_info.components["myzlib"].set_property("cmake_target_name",
                                                                    "ZLIB::zmylib")
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class App(ConanFile):
            name = "app"
            version = "0.1"
            settings = "build_type"
            requires = "zlib/0.1"
            generators = "CMakeDeps"

            def generate(self):
                self.output.info(f"DEP ZLIB generate: {self.dependencies['zlib'].ref.name}!")
            def build(self):
                self.output.info(f"DEP ZLIB build: {self.dependencies['zlib'].ref.name}!")
            def package_info(self):
                self.output.info(f"zlib in deps?: {'zlib' in self.dependencies}")
                self.output.info(f"zlib-ng in deps?: {'zlib-ng' in self.dependencies}")
                self.output.info(f"DEP ZLIB package_info: {self.dependencies['zlib'].ref.name}!")
                self.cpp_info.requires = ["zlib::myzlib"]
        """)
    profile = textwrap.dedent("""
        [options]
        zlib-ng/*:compat=True

        [replace_requires]
        zlib/0.1: zlib-ng/0.1
        """)
    c.save({"zlibng/conanfile.py": zlib_ng,
            "app/conanfile.py": conanfile,
            "profile": profile})

    c.run("create zlibng -o *:compat=True")
    c.run("build app -pr=profile")
    assert "zlib/0.1: zlib-ng/0.1" in c.out
    assert "DEP ZLIB generate: zlib-ng!" in c.out
    assert "conanfile.py (app/0.1): DEP ZLIB build: zlib-ng!" in c.out
    # Check generated CMake code. If the targets are NOT compatible, then the replacement
    # Cannot happen
    assert "find_package(ZLIB)" in c.out
    assert "target_link_libraries(... ZLIB::ZLIB)" in c.out
    cmake = c.load("app/ZLIBTargets.cmake")
    assert "add_library(ZLIB::ZLIB INTERFACE IMPORTED)" in cmake
    cmake = c.load("app/ZLIB-Target-none.cmake")
    assert "set_property(TARGET ZLIB::ZLIB APPEND PROPERTY INTERFACE_LINK_LIBRARIES ZLIB::zmylib)" \
           in cmake

    c.run("create app -pr=profile")
    assert "zlib/0.1: zlib-ng/0.1" in c.out
    assert "DEP ZLIB generate: zlib-ng!" in c.out
    assert "app/0.1: DEP ZLIB build: zlib-ng!" in c.out
    assert "find_package(ZLIB)" in c.out
    assert "target_link_libraries(... ZLIB::ZLIB)" in c.out
    assert "zlib in deps?: True" in c.out
    assert "zlib-ng in deps?: False" in c.out


def test_replace_requires_multiple():
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class EpoxyConan(ConanFile):
            name = "libepoxy"
            version = "0.1"

            def requirements(self):
                self.requires("opengl/system")
                self.requires("egl/system")

            def generate(self):
                for r, d in self.dependencies.items():
                    self.output.info(f"DEP: {r.ref.name}: {d.ref.name}")

            def package_info(self):
                self.cpp_info.requires.append("opengl::opengl")
                self.cpp_info.requires.append("egl::egl")
        """)
    profile = textwrap.dedent("""
        [replace_requires]
        opengl/system: libgl/1.0
        egl/system: libgl/1.0
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "app/conanfile.py": conanfile,
            "profile": profile})
    c.run("create dep --name=libgl --version=1.0")
    c.run("create app -pr=profile")
    # There are actually 2 dependencies, pointing to the same node
    assert "DEP: opengl: libgl" in c.out
    assert "DEP: egl: libgl" in c.out


class TestReplaceRequiresTransitiveGenerators:
    """ Generators are incorrectly managing replace_requires
    # https://github.com/conan-io/conan/issues/17557
    """

    @pytest.mark.parametrize("diamond", [True, False])
    def test_no_components(self, diamond):
        c = TestClient()
        zlib_ng = textwrap.dedent("""
            from conan import ConanFile
            class ZlibNG(ConanFile):
                name = "zlib-ng"
                version = "0.1"
                package_type = "static-library"
                def package_info(self):
                    self.cpp_info.libs = ["zlib"]
                    self.cpp_info.type = "static-library"
                    self.cpp_info.location = "lib/zlib.lib"
                    self.cpp_info.set_property("cmake_file_name", "ZLIB")
                    self.cpp_info.set_property("cmake_target_name", "ZLIB::ZLIB")
                    self.cpp_info.set_property("pkg_config_name", "ZLIB")
            """)
        openssl = textwrap.dedent("""
            from conan import ConanFile
            class openssl(ConanFile):
                name = "openssl"
                version = "0.1"
                package_type = "static-library"
                requires = "zlib/0.1"
                def package_info(self):
                    self.cpp_info.libs = ["crypto"]
                    self.cpp_info.type = "static-library"
                    self.cpp_info.location = "lib/crypto.lib"
                    self.cpp_info.requires = ["zlib::zlib"]
            """)
        zlib = '"zlib/0.1"' if diamond else ""
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            class App(ConanFile):
                name = "app"
                version = "0.1"
                settings = "build_type", "arch"
                requires = "openssl/0.1", {zlib}
                package_type = "application"
                generators = "CMakeConfigDeps", "PkgConfigDeps", "MSBuildDeps"
            """)
        profile = textwrap.dedent("""
            [settings]
            build_type = Release
            arch=x86_64

            [replace_requires]
            zlib/0.1: zlib-ng/0.1
            """)
        c.save({"zlibng/conanfile.py": zlib_ng,
                "openssl/conanfile.py": openssl,
                "app/conanfile.py": conanfile,
                "profile": profile})

        c.run("create zlibng")
        c.run("create openssl -pr=profile")
        c.run("install app -pr=profile")
        assert "zlib/0.1: zlib-ng/0.1" in c.out

        pc_content = c.load("app/ZLIB.pc")
        assert 'Libs: -L"${libdir}" -lzlib' in pc_content
        pc_content = c.load("app/openssl.pc")
        assert 'Requires: ZLIB' in pc_content

        cmake = c.load("app/ZLIB-Targets-release.cmake")
        assert "add_library(ZLIB::ZLIB STATIC IMPORTED)" in cmake

        cmake = c.load("app/openssl-Targets-release.cmake")
        assert "find_dependency(ZLIB REQUIRED CONFIG)" in cmake
        assert "add_library(openssl::openssl STATIC IMPORTED)" in cmake
        assert "set_property(TARGET openssl::openssl APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
               '             "$<$<CONFIG:RELEASE>:ZLIB::ZLIB>")' in cmake

        # checking MSBuildDeps
        zlib_ng_props = c.load("app/conan_zlib-ng.props")
        assert 'Project="conan_zlib-ng_release_x64.props"' in zlib_ng_props
        props = c.load("app/conan_openssl_release_x64.props")
        assert "<Import Condition=\"'$(conan_zlib-ng_props_imported)' != 'True'\"" \
               " Project=\"conan_zlib-ng.props\"/>" in props

    @pytest.mark.parametrize("diamond", [True, False])
    def test_openssl_components(self, diamond):
        c = TestClient()
        zlib_ng = textwrap.dedent("""
            from conan import ConanFile
            class ZlibNG(ConanFile):
                name = "zlib-ng"
                version = "0.1"
                package_type = "static-library"
                def package_info(self):
                    self.cpp_info.libs = ["zlib"]
                    self.cpp_info.type = "static-library"
                    self.cpp_info.location = "lib/zlib.lib"
                    self.cpp_info.set_property("cmake_file_name", "ZLIB")
                    self.cpp_info.set_property("cmake_target_name", "ZLIB::ZLIB")
                    self.cpp_info.set_property("pkg_config_name", "ZLIB")
            """)
        openssl = textwrap.dedent("""
            from conan import ConanFile
            class openssl(ConanFile):
                name = "openssl"
                version = "0.1"
                package_type = "static-library"
                requires = "zlib/0.1"
                def package_info(self):
                    self.cpp_info.components["crypto"].libs = ["crypto"]
                    self.cpp_info.components["crypto"].type = "static-library"
                    self.cpp_info.components["crypto"].location = "lib/crypto.lib"
                    self.cpp_info.components["crypto"].requires = ["zlib::zlib"]
            """)
        zlib = '"zlib/0.1"' if diamond else ""
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            class App(ConanFile):
                name = "app"
                version = "0.1"
                settings = "build_type", "arch"
                requires = "openssl/0.1", {zlib}
                package_type = "application"
                generators = "CMakeConfigDeps", "PkgConfigDeps", "MSBuildDeps"
            """)
        profile = textwrap.dedent("""
            [settings]
            build_type = Release
            arch=x86_64

            [replace_requires]
            zlib/0.1: zlib-ng/0.1
            """)
        c.save({"zlibng/conanfile.py": zlib_ng,
                "openssl/conanfile.py": openssl,
                "app/conanfile.py": conanfile,
                "profile": profile})

        c.run("create zlibng")
        c.run("create openssl -pr=profile")
        c.run("install app -pr=profile")
        assert "zlib/0.1: zlib-ng/0.1" in c.out

        pc_content = c.load("app/ZLIB.pc")
        assert 'Libs: -L"${libdir}" -lzlib' in pc_content
        pc_content = c.load("app/openssl-crypto.pc")
        assert 'Requires: ZLIB' in pc_content

        cmake = c.load("app/ZLIB-Targets-release.cmake")
        assert "add_library(ZLIB::ZLIB STATIC IMPORTED)" in cmake

        cmake = c.load("app/openssl-Targets-release.cmake")
        assert "find_dependency(ZLIB REQUIRED CONFIG)" in cmake
        assert "add_library(openssl::crypto STATIC IMPORTED)" in cmake
        assert "set_property(TARGET openssl::crypto APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
               '             "$<$<CONFIG:RELEASE>:ZLIB::ZLIB>")' in cmake

        # checking MSBuildDeps
        zlib_ng_props = c.load("app/conan_zlib-ng.props")
        assert 'Project="conan_zlib-ng_release_x64.props"' in zlib_ng_props

        props = c.load("app/conan_openssl_crypto_release_x64.props")
        assert "<Import Condition=\"'$(conan_zlib-ng_props_imported)' != 'True'\"" \
               " Project=\"conan_zlib-ng.props\"/>" in props

    @pytest.mark.parametrize("diamond", [True, False])
    @pytest.mark.parametrize("explicit_requires", [True, False])
    def test_zlib_components(self, diamond, explicit_requires):
        c = TestClient()
        zlib_ng = textwrap.dedent("""
            from conan import ConanFile
            class ZlibNG(ConanFile):
                name = "zlib-ng"
                version = "0.1"
                package_type = "static-library"
                def package_info(self):
                    self.cpp_info.components["myzlib"].libs = ["zlib"]
                    self.cpp_info.components["myzlib"].type = "static-library"
                    self.cpp_info.components["myzlib"].location = "lib/zlib.lib"
                    self.cpp_info.set_property("cmake_file_name", "ZLIB")
                    self.cpp_info.components["myzlib"].set_property("pkg_config_name", "ZLIB")
                    self.cpp_info.components["myzlib"].set_property("cmake_target_name",
                                                                    "ZLIB::ZLIB")
            """)
        openssl = textwrap.dedent(f"""
            from conan import ConanFile
            class openssl(ConanFile):
                name = "openssl"
                version = "0.1"
                package_type = "static-library"
                requires = "zlib/0.1"
                def package_info(self):
                    self.cpp_info.libs = ["crypto"]
                    self.cpp_info.type = "static-library"
                    self.cpp_info.location = "lib/crypto.lib"
                    if {explicit_requires}:
                        self.cpp_info.requires = ["zlib::zlib"]
            """)
        zlib = '"zlib/0.1"' if diamond else ""
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            class App(ConanFile):
                name = "app"
                version = "0.1"
                settings = "build_type", "arch"
                requires = "openssl/0.1", {zlib}
                package_type = "application"
                generators = "CMakeConfigDeps", "PkgConfigDeps", "MSBuildDeps"
            """)
        profile = textwrap.dedent("""
            [settings]
            build_type = Release
            arch = x86_64

            [replace_requires]
            zlib/0.1: zlib-ng/0.1
            """)
        c.save({"zlibng/conanfile.py": zlib_ng,
                "openssl/conanfile.py": openssl,
                "app/conanfile.py": conanfile,
                "profile": profile})

        c.run("create zlibng")
        c.run("create openssl -pr=profile")
        c.run("install app -pr=profile")
        assert "zlib/0.1: zlib-ng/0.1" in c.out

        pc_content = c.load("app/zlib-ng.pc")
        assert 'Requires: ZLIB' in pc_content
        pc_content = c.load("app/ZLIB.pc")
        assert 'Libs: -L"${libdir}" -lzlib' in pc_content
        pc_content = c.load("app/openssl.pc")
        assert 'Requires: zlib-ng' in pc_content

        cmake = c.load("app/ZLIB-Targets-release.cmake")
        assert "add_library(ZLIB::ZLIB STATIC IMPORTED)" in cmake

        cmake = c.load("app/openssl-Targets-release.cmake")
        assert "find_dependency(ZLIB REQUIRED CONFIG)" in cmake
        assert "add_library(openssl::openssl STATIC IMPORTED)" in cmake
        # It should access the generic zlib-ng target
        assert "set_property(TARGET openssl::openssl APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
               '             "$<$<CONFIG:RELEASE>:zlib-ng::zlib-ng>")' in cmake

        # checking MSBuildDeps
        zlib_ng_props = c.load("app/conan_zlib-ng.props")
        assert "<Import Condition=\"'$(conan_zlib-ng_myzlib_props_imported)' != 'True'\" " \
               "Project=\"conan_zlib-ng_myzlib.props\"/" in zlib_ng_props

        props = c.load("app/conan_openssl_release_x64.props")
        assert "<Import Condition=\"'$(conan_zlib-ng_props_imported)' != 'True'\"" \
               " Project=\"conan_zlib-ng.props\"/>" in props

    @pytest.mark.parametrize("diamond", [True, False])
    @pytest.mark.parametrize("package_requires", [False, True])
    def test_both_components(self, diamond, package_requires):
        c = TestClient()
        zlib_ng = textwrap.dedent("""
            from conan import ConanFile
            class ZlibNG(ConanFile):
                name = "zlib-ng"
                version = "0.1"
                package_type = "static-library"
                def package_info(self):
                    self.cpp_info.components["myzlib"].libs = ["zlib"]
                    self.cpp_info.components["myzlib"].type = "static-library"
                    self.cpp_info.components["myzlib"].location = "lib/zlib.lib"
                    self.cpp_info.set_property("cmake_file_name", "ZLIB")
                    self.cpp_info.components["myzlib"].set_property("pkg_config_name", "ZLIB")
                    self.cpp_info.components["myzlib"].set_property("cmake_target_name",
                                                                    "ZLIB::ZLIB")
            """)
        openssl = textwrap.dedent(f"""
            from conan import ConanFile
            class openssl(ConanFile):
                name = "openssl"
                version = "0.1"
                package_type = "static-library"
                requires = "zlib/0.1"
                def package_info(self):
                    self.cpp_info.components["crypto"].libs = ["crypto"]
                    self.cpp_info.components["crypto"].type = "static-library"
                    self.cpp_info.components["crypto"].location = "lib/crypto.lib"
                    if {package_requires}:
                        self.cpp_info.components["crypto"].requires = ["zlib::zlib"]
                    else:
                        self.cpp_info.components["crypto"].requires = ["zlib::myzlib"]
            """)
        zlib = '"zlib/0.1"' if diamond else ""
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            class App(ConanFile):
                name = "app"
                version = "0.1"
                settings = "build_type", "arch"
                requires = "openssl/0.1", {zlib}
                package_type = "application"
                generators = "CMakeConfigDeps", "PkgConfigDeps", "MSBuildDeps"
            """)
        profile = textwrap.dedent("""
            [settings]
            build_type = Release
            arch = x86_64

            [replace_requires]
            zlib/0.1: zlib-ng/0.1
            """)
        c.save({"zlibng/conanfile.py": zlib_ng,
                "openssl/conanfile.py": openssl,
                "app/conanfile.py": conanfile,
                "profile": profile})

        c.run("create zlibng")
        c.run("create openssl -pr=profile")
        c.run("install app -pr=profile")
        assert "zlib/0.1: zlib-ng/0.1" in c.out

        pc_content = c.load("app/zlib-ng.pc")
        assert 'Requires: ZLIB' in pc_content
        pc_content = c.load("app/ZLIB.pc")
        assert 'Libs: -L"${libdir}" -lzlib' in pc_content
        pc_content = c.load("app/openssl-crypto.pc")
        assert f'Requires: {"zlib-ng" if package_requires else "ZLIB"}' in pc_content

        cmake = c.load("app/ZLIB-Targets-release.cmake")
        assert "add_library(ZLIB::ZLIB STATIC IMPORTED)" in cmake

        cmake = c.load("app/openssl-Targets-release.cmake")
        assert "find_dependency(ZLIB REQUIRED CONFIG)" in cmake
        assert "add_library(openssl::crypto STATIC IMPORTED)" in cmake
        if package_requires:
            # The generic package requirement uses the package name zlib-ng
            assert "set_property(TARGET openssl::crypto APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
                   '             "$<$<CONFIG:RELEASE>:zlib-ng::zlib-ng>")' in cmake
        else:
            assert "set_property(TARGET openssl::crypto APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
                   '             "$<$<CONFIG:RELEASE>:ZLIB::ZLIB>")' in cmake

        # checking MSBuildDeps
        zlib_ng_props = c.load("app/conan_zlib-ng.props")
        assert "<Import Condition=\"'$(conan_zlib-ng_myzlib_props_imported)' != 'True'\" " \
               "Project=\"conan_zlib-ng_myzlib.props\"/" in zlib_ng_props

        props = c.load("app/conan_openssl_crypto_release_x64.props")
        if package_requires:
            assert "<Import Condition=\"'$(conan_zlib-ng_props_imported)' != 'True'\"" \
                   " Project=\"conan_zlib-ng.props\"/>" in props
        else:
            assert "<Import Condition=\"'$(conan_zlib-ng_myzlib_props_imported)' != 'True'\"" \
                   " Project=\"conan_zlib-ng_myzlib.props\"/>" in props


@pytest.mark.parametrize("require, pattern, alternative, expected", [
     # Version range as pattern
     # PINNED REQUIRE VERSION
     ("dep/1.0", "dep/[>=1.0 <2]", "dep/1.3", "dep/1.3"),
     ("dep/1.0", "dep/[>=1.5 <2]", "dep/1.3", False),
     # RANGE REQUIRE VERSION
     ("dep/[>=1.2 <2]", "dep/[>=1.0 <2]", "dep/1.3", "dep/1.3"),
     ("dep/[>=1.0 <1.5]", "dep/[>=1.2 <2]", "dep/1.3", "dep/1.3"),
     ("dep/[>=1.0 <1.5]", "dep/[>=1.5 <2]", "dep/1.3", False)
    ]
 )
def test_replace_requires_ranges(require, pattern, alternative, expected):
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "app/conanfile.py": GenConanfile().with_requires(require),
            "profile": f"[replace_requires]\n{pattern}: {alternative}"})
    c.run("create dep --version=1.0")
    c.run("create dep --version=1.3")
    c.run("graph info app -pr=profile")
    if expected:
        assert "Replaced requires" in c.out
        assert f"{require}: {expected}" in c.out
    else:
        assert "Replaced requires" not in c.out


def test_host_version_replace():
    profile = textwrap.dedent("""
    include(default)
    [replace_requires]
    pkg/*: pkg/0.1@user/channel
    """)

    tc = TestClient(light=True)
    tc.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
             "conanfile.py": GenConanfile()
                .with_requires("pkg/0.1@user/channel")
                .with_tool_requires("pkg/<host_version>"),
             "profile": profile})
    tc.run("create pkg")
    tc.run("create pkg --user=user --channel=channel")

    # We did not track the user/channel, we resolve the version but keep the original user/channel
    tc.run("install -pr=profile")
    tc.assert_listed_require({"pkg/0.1@user/channel#485dad6cb11e2fa99d9afbe44a57a164": "Cache"})
    tc.assert_listed_require({"pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164": "Cache"}, build=True)

    # If we want to also match user/channel
    # Solution 1: Also replace the tool_requires in your profile to use same user/channel
    tool_profile = profile + "\n[replace_tool_requires]\npkg/*: pkg/<host_version>@user/channel"
    tc.save({"tool_profile": tool_profile})
    tc.run("install -pr=tool_profile")
    tc.assert_listed_require({"pkg/0.1@user/channel#485dad6cb11e2fa99d9afbe44a57a164": "Cache"})
    tc.assert_listed_require({"pkg/0.1@user/channel#485dad6cb11e2fa99d9afbe44a57a164": "Cache"}, build=True)

    # Solution 2: Directly in the requirement
    tc.save({"conanfile.py": GenConanfile()
                .with_requires("pkg/0.1@user/channel")
                .with_tool_requires("pkg/<host_version>@user/channel")})

    tc.run("install -pr=profile")
    tc.assert_listed_require({"pkg/0.1@user/channel#485dad6cb11e2fa99d9afbe44a57a164": "Cache"})
    tc.assert_listed_require({"pkg/0.1@user/channel#485dad6cb11e2fa99d9afbe44a57a164": "Cache"}, build=True)


class TestReplaceRequiresCompose:
    def test_rules_merged_from_multiple_profiles(self):
        """[replace_requires] rules from multiple -pr profiles are merged into one combined
        ruleset, each rule independently applied."""
        c = TestClient(light=True)
        c.save({"zlib/conanfile.py": GenConanfile("zlib"),
                "openssl/conanfile.py": GenConanfile("openssl"),
                "app/conanfile.py": GenConanfile().with_requires("zlib/1.0", "openssl/1.0"),
                "profile1": "[replace_requires]\nzlib/1.0: zlib/2.0",
                "profile2": "[replace_requires]\nopenssl/1.0: openssl/2.0"})
        c.run("create zlib --version=1.0")
        c.run("create zlib --version=2.0")
        c.run("create openssl --version=1.0")
        c.run("create openssl --version=2.0")

        # Both profiles: rules are merged, each replacement is independently applied
        c.run("install app -pr=profile1 -pr=profile2")
        assert "zlib/1.0: zlib/2.0" in c.out
        assert "openssl/1.0: openssl/2.0" in c.out
        c.assert_listed_require({"zlib/2.0": "Cache"})
        c.assert_listed_require({"openssl/2.0": "Cache"})

        # Only profile1: only zlib is replaced
        c.run("install app -pr=profile1")
        assert "zlib/1.0: zlib/2.0" in c.out
        assert "openssl/1.0: openssl/2.0" not in c.out
        c.assert_listed_require({"zlib/2.0": "Cache"})
        c.assert_listed_require({"openssl/1.0": "Cache"})

        # Only profile2: only openssl is replaced
        c.run("install app -pr=profile2")
        assert "zlib/1.0: zlib/2.0" not in c.out
        assert "openssl/1.0: openssl/2.0" in c.out
        c.assert_listed_require({"zlib/1.0": "Cache"})
        c.assert_listed_require({"openssl/2.0": "Cache"})

    def test_no_chaining(self):
        """Replacements are applied in a single pass — results are NOT re-evaluated, so
        profile1: A->B plus profile2: B->C does not transitively replace A->C."""
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": GenConanfile("dep"),
                "app/conanfile.py": GenConanfile().with_requires("dep/1.0"),
                "profile1": "[replace_requires]\ndep/1.0: dep/2.0",
                "profile2": "[replace_requires]\ndep/2.0: dep/3.0"})
        c.run("create dep --version=2.0")
        c.run("create dep --version=3.0")

        # dep/1.0 is replaced to dep/2.0 by profile1's rule; the dep/2.0->dep/3.0 rule from
        # profile2 is present in the merged set but is NOT applied again to the already-replaced ref
        c.run("install app -pr=profile1 -pr=profile2")
        assert "dep/1.0: dep/2.0" in c.out
        c.assert_listed_require({"dep/2.0": "Cache"})

    def test_last_profile_wins_on_same_pattern(self):
        """When two profiles define a replacement for the same pattern, the last profile wins."""
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": GenConanfile("dep"),
                "app/conanfile.py": GenConanfile().with_requires("dep/1.0"),
                "profile1": "[replace_requires]\ndep/1.0: dep/2.0",
                "profile2": "[replace_requires]\ndep/1.0: dep/3.0"})
        c.run("create dep --version=2.0")
        c.run("create dep --version=3.0")

        c.run("install app -pr=profile1 -pr=profile2")
        assert "dep/1.0: dep/3.0" in c.out
        c.assert_listed_require({"dep/3.0": "Cache"})

    @pytest.mark.parametrize("tool_require", [False, True])
    @pytest.mark.parametrize("strategy", ["cli", "include"])
    def test_invalidate(self, strategy, tool_require):
        """'pattern: !' removes a replace_requires/replace_tool_requires rule defined in an
        earlier profile, whether composed via -pr=p1 -pr=p2 (cli) or include(p1) (include)."""
        section = "replace_tool_requires" if tool_require else "replace_requires"
        app = GenConanfile().with_tool_requires("dep/1.0") if tool_require \
            else GenConanfile().with_requires("dep/1.0")
        profile1 = f"[{section}]\ndep/1.0: dep/2.0"
        if strategy == "cli":
            profile2 = f"[{section}]\ndep/1.0: !"
            both_cmd = "install app -pr=profile1 -pr=profile2"
        else:
            profile2 = f"include(profile1)\n[{section}]\ndep/1.0: !"
            both_cmd = "install app -pr=profile2"
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": GenConanfile("dep"), "app/conanfile.py": app,
                "profile1": profile1, "profile2": profile2})
        c.run("create dep --version=1.0")
        c.run("create dep --version=2.0")

        # profile1 alone: replacement is active
        c.run("install app -pr=profile1")
        assert "dep/1.0: dep/2.0" in c.out
        c.assert_listed_require({"dep/2.0": "Cache"}, build=tool_require)

        # profile2 cancels the rule from profile1: original dep/1.0 is used
        c.run(both_cmd)
        assert "dep/1.0: dep/2.0" not in c.out
        c.assert_listed_require({"dep/1.0": "Cache"}, build=tool_require)

    def test_invalidate_all(self):
        """'*: !' invalidates all replace_requires rules defined in earlier profiles at once."""
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": GenConanfile("dep"),
                "app/conanfile.py": GenConanfile().with_requires("dep/1.0", "dep2/1.0"),
                "dep2/conanfile.py": GenConanfile("dep2"),
                "profile1": "[replace_requires]\ndep/1.0: dep/2.0\ndep2/1.0: dep2/2.0",
                "profile2": "[replace_requires]\n*: !"})
        c.run("create dep --version=1.0")
        c.run("create dep --version=2.0")
        c.run("create dep2 --version=1.0")
        c.run("create dep2 --version=2.0")

        # profile1 alone: both replacements active
        c.run("install app -pr=profile1")
        assert "dep/1.0: dep/2.0" in c.out
        assert "dep2/1.0: dep2/2.0" in c.out
        c.assert_listed_require({"dep/2.0": "Cache"})
        c.assert_listed_require({"dep2/2.0": "Cache"})

        # profile2 wipes all rules: both original requirements are used
        c.run("install app -pr=profile1 -pr=profile2")
        assert "dep/1.0: dep/2.0" not in c.out
        assert "dep2/1.0: dep2/2.0" not in c.out
        c.assert_listed_require({"dep/1.0": "Cache"})
        c.assert_listed_require({"dep2/1.0": "Cache"})


class TestReplaceRequiresCLIPriority:
    """CLI-specified requires (--requires, --tool-requires, conan create ref) have higher priority
    than [replace_requires] / [replace_tool_requires] profile sections and must not be replaced."""

    def test_install_requires_cli_not_replaced(self):
        """conan install --requires=pkg/1.0 should install pkg/1.0, not the replacement."""
        c = TestClient(light=True)
        c.save({"pkg/conanfile.py": GenConanfile("pkg", "1.0"),
                "other/conanfile.py": GenConanfile("other", "2.0"),
                "profile": "[replace_requires]\npkg/*: other/2.0"})
        c.run("create pkg")
        c.run("create other")
        c.run("install --requires=pkg/1.0 -pr=profile")
        # The CLI-specified pkg/1.0 must not be replaced by other/2.0
        assert "Replaced requires" not in c.out
        c.assert_listed_require({"pkg/1.0": "Cache"})

    def test_install_tool_requires_cli_not_replaced(self):
        """conan install --tool-requires=cmake/3.20 should use cmake/3.20, not the replacement."""
        c = TestClient(light=True)
        c.save({"cmake/conanfile.py": GenConanfile("cmake", "3.20"),
                "cmake_old/conanfile.py": GenConanfile("cmake", "3.19"),
                "profile": "[replace_tool_requires]\ncmake/*: cmake/3.19"})
        c.run("create cmake")
        c.run("create cmake_old --name=cmake --version=3.19")
        c.run("install --tool-requires=cmake/3.20 -pr=profile")
        # The CLI-specified cmake/3.20 must not be replaced by cmake/3.19
        assert "Replaced requires" not in c.out
        c.assert_listed_require({"cmake/3.20": "Cache"}, build=True)

    def test_create_cli_not_replaced(self):
        """conan create --name=pkg --version=1.0 should create pkg/1.0, not the replacement."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile(),
                "other/conanfile.py": GenConanfile("other", "2.0"),
                "profile": "[replace_requires]\npkg/*: other/2.0"})
        c.run("create other")
        # Creating pkg/1.0 should not be affected by the replace_requires targeting pkg/*
        c.run("create . --name=pkg --version=1.0 -pr=profile")
        assert "Replaced requires" not in c.out
        assert "pkg/1.0" in c.out

    def test_create_build_require_cli_not_replaced(self):
        """conan create --build-require --name=cmake --version=3.20 should create cmake/3.20."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile(),
                "old/conanfile.py": GenConanfile("cmake", "3.19"),
                "profile": "[replace_tool_requires]\ncmake/*: cmake/3.19"})
        c.run("create old --name=cmake --version=3.19")
        c.run("create . --name=cmake --version=3.20 --build-require -pr=profile")
        assert "Replaced requires" not in c.out
        assert "cmake/3.20" in c.out

    def test_install_requires_cli_transitive_still_replaced(self):
        """Transitive dependencies of CLI-specified requires SHOULD still be replaced."""
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": GenConanfile("dep", "2.0"),
                "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                "profile": "[replace_requires]\ndep/*: dep/2.0"})
        c.run("create dep")
        c.run("create pkg --build=missing -pr=profile")
        # Install pkg/1.0 from CLI - pkg itself is not replaced, but its dep/1.0 IS replaced
        c.run("install --requires=pkg/1.0 -pr=profile")
        assert "Replaced requires" in c.out
        c.assert_listed_require({"pkg/1.0": "Cache"})
        c.assert_listed_require({"dep/2.0": "Cache"})

    def test_install_requires_cli_name_change_not_replaced(self):
        """conan install --requires=pkg/1.0 should not be replaced even if name changes."""
        c = TestClient(light=True)
        c.save({"pkg/conanfile.py": GenConanfile("pkg", "1.0"),
                "pkgng/conanfile.py": GenConanfile("pkgng", "1.0"),
                "profile": "[replace_requires]\npkg/*: pkgng/*"})
        c.run("create pkg")
        c.run("create pkgng")
        c.run("install --requires=pkg/1.0 -pr=profile")
        # CLI-specified pkg/1.0 must not be replaced by pkgng/1.0
        assert "Replaced requires" not in c.out
        c.assert_listed_require({"pkg/1.0": "Cache"})
