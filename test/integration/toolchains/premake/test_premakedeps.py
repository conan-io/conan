import textwrap
import pytest
import os

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def assert_vars_file(client, configuration):
    contents = client.load(f"conan_pkg.name-more+_vars_{configuration}_x86_64.premake5.lua")
    assert f'include "conanutils.premake5.lua"' in contents
    assert f't_conandeps = {{}}' in contents
    assert f't_conandeps["{configuration}_x86_64"] = {{}}' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"] = {{}}' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["includedirs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["libdirs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["bindirs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["libs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["system_libs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["defines"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["cxxflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["cflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["sharedlinkflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["exelinkflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["frameworks"]' in contents
    assert f'if conandeps == nil then conandeps = {{}} end' in contents
    assert f'conan_premake_tmerge(conandeps, t_conandeps)' in contents


def test_premakedeps():
    # Create package
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg.name-more+"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["libmpdecimal++"].libs = ["libmp++"]
                self.cpp_info.components["mycomp.some-comp+"].libs = ["mylib"]
                self.cpp_info.components["libmpdecimal++"].requires = ["mycomp.some-comp+"]
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . -s arch=x86_64 -s build_type=Debug")
    client.run("create . -s arch=x86_64 -s build_type=Release")

    # Run conan
    client.run("install --require=pkg.name-more+/1.0@ -g PremakeDeps -s arch=x86_64 -s build_type=Debug")
    client.run("install --require=pkg.name-more+/1.0@ -g PremakeDeps -s arch=x86_64 -s build_type=Release")

    # Assert root lua file
    contents = client.load("conandeps.premake5.lua")
    assert 'include "conan_pkg.name-more+.premake5.lua"' in contents
    assert 'function conan_setup_build(conf, pkg)' in contents
    assert 'function conan_setup_link(conf, pkg)' in contents
    assert 'function conan_setup(conf, pkg)' in contents

    # Assert package root file
    contents = client.load("conan_pkg.name-more+.premake5.lua")
    assert 'include "conan_pkg.name-more+_vars_debug_x86_64.premake5.lua"' in contents
    assert 'include "conan_pkg.name-more+_vars_release_x86_64.premake5.lua"' in contents

    # Assert package per configuration files
    assert_vars_file(client, 'debug')
    assert_vars_file(client, 'release')


def test_premakedeps_link_order():
    client = TestClient()
    profile = textwrap.dedent(
        """
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++
        build_type=Release
        """)
    client.save(
        {
            "liba/conanfile.py": GenConanfile("liba")
            .with_settings("os", "compiler", "build_type", "arch")
            .with_version("1.0")
            .with_generator("PremakeDeps")
            .with_generator("PremakeToolchain")
            .with_package_info(cpp_info={"libs": ["liba"]}),

            "libb/conanfile.py": GenConanfile("libb")
            .with_settings("os", "compiler", "build_type", "arch")
            .with_version("1.0")
            .with_requires("liba/1.0")
            .with_generator("PremakeDeps")
            .with_package_info(
                cpp_info={
                    "components": {
                        "libb1": {"requires": ["liba::liba"]},
                        "libb2": {"requires": ["libb1"]},
                    }
                }
            ),

            "libc/conanfile.py": GenConanfile("libc")
            .with_settings("os", "compiler", "build_type", "arch")
            .with_version("1.0")
            .with_requires("libb/1.0")
            .with_generator("PremakeDeps")
            .with_package_info(cpp_info={"libs": ["libc"]}),

            "consumer/conanfile.py": GenConanfile("consumer")
            .with_settings("os", "compiler", "build_type", "arch")
            .with_version("1.0")
            .with_requires("libc/1.0")
            .with_generator("PremakeDeps"),

            "profile": profile
        }
    )
    client.run("create liba -pr profile")
    client.run("create libb -pr profile")
    client.run("create libc -pr profile")
    client.run("install consumer -pr profile")
    contents = client.load("consumer/conanconfig.premake5.lua")
    assert 'include "conanconfig_release_x86_64.premake5.lua"' in contents
    contents = client.load("consumer/conanconfig_release_x86_64.premake5.lua")
    # Check correct order of dependencies: more dependent libs should be linked first
    assert 't_conan_deps_order["release_x86_64"] = {"libc", "libb", "liba"}' in contents

    # Check previous configurations are preserved when installing new configuration
    client.run("install consumer -pr profile -s build_type=Debug --build=missing")
    contents = client.load("consumer/conanconfig.premake5.lua")
    assert 'include "conanconfig_release_x86_64.premake5.lua"' in contents
    assert 'include "conanconfig_debug_x86_64.premake5.lua"' in contents
    contents = client.load("consumer/conanconfig_debug_x86_64.premake5.lua")
    assert 't_conan_deps_order["debug_x86_64"] = {"libc", "libb", "liba"}' in contents

@pytest.mark.parametrize("transitive_headers", [True, False])
@pytest.mark.parametrize("transitive_libs", [True, False])
@pytest.mark.parametrize("brotli_package_type", ["unknown", "static-library", "shared-library"])
@pytest.mark.parametrize("lib_package_type", ["unknown", "static-library", "shared-library"])
def test_premakedeps_traits(transitive_headers, transitive_libs, brotli_package_type, lib_package_type):
    client = TestClient()
    profile = textwrap.dedent(
        """
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++
        build_type=Release
        """)

    client.save(
        {
            "brotli/conanfile.py": GenConanfile("brotli", "1.0")
            .with_package_type(brotli_package_type)
            .with_package_info(
                {"libs": ["brotlienc2"]}
            ),
            "lib/conanfile.py": GenConanfile("lib", "1.0")
            .with_package_type(lib_package_type)
            .with_requirement(
                "brotli/1.0",
                transitive_headers=transitive_headers,
                transitive_libs=transitive_libs,
            ),
            "conanfile.py": GenConanfile("app", "1.0")
            .with_settings("os", "compiler", "build_type", "arch")
            .with_require("lib/1.0")
            .with_generator("PremakeDeps"),
            "profile": profile,
        }
    )
    client.run("create brotli -pr profile")
    brotli_layout = client.created_layout()
    client.run("create lib -pr profile")
    client.run("install . -pr profile")

    if not transitive_headers and not transitive_libs and brotli_package_type != "shared-library":
        assert not os.path.exists(os.path.join(client.current_folder, "conan_brotli_vars_release_x86_64.premake5.lua"))
        return

    brotli_vars = client.load("conan_brotli_vars_release_x86_64.premake5.lua")
    if transitive_libs:
        assert 't_conandeps["release_x86_64"]["brotli"]["libs"] = {"brotlienc2"}' in brotli_vars
    else:
        assert 't_conandeps["release_x86_64"]["brotli"]["libs"] = {}' in brotli_vars

    if transitive_headers:
        include_path = os.path.join(brotli_layout.package(), "include").replace("\\", "/")
        assert f't_conandeps["release_x86_64"]["brotli"]["includedirs"] = {{"{include_path}"}}' in brotli_vars
    else:
        assert 't_conandeps["release_x86_64"]["brotli"]["includedirs"] = {}' in brotli_vars
