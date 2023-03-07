import textwrap
import os

from conans.test.utils.tools import TestClient

def assert_configuration_file(client, configuration):
    contents = client.load(f"conan_pkg.name-more+_{configuration}_x86_64.premake5.lua")
    assert f'include "conan_pkg.name-more+_vars_{configuration}_x86_64.premake5.lua"' in contents
    assert f'function conan_setup_build_pkg.name-more+_{configuration}_x86_64()' in contents
    assert f'function conan_setup_link_pkg.name-more+_{configuration}_x86_64()' in contents
    assert f'function conan_setup_pkg.name-more+_{configuration}_x86_64()' in contents

def assert_vars_file(client, configuration):
    contents = client.load(f"conan_pkg.name-more+_vars_{configuration}_x86_64.premake5.lua")
    assert f'conan_includedirs_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_libdirs_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_bindirs_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_libs_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_system_libs_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_defines_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_cxxflags_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_cflags_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_sharedlinkflags_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_exelinkflags_pkg.name-more+_{configuration}_x86_64' in contents
    assert f'conan_frameworks_pkg.name-more+_{configuration}_x86_64' in contents

def test_premakedeps():
    # Create package
    client = TestClient()
    print(client.current_folder)
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
    assert 'function conan_setup_build()' in contents
    assert 'function conan_setup_link()' in contents
    assert 'function conan_setup()' in contents

    # Assert package root file
    contents = client.load("conan_pkg.name-more+.premake5.lua")
    assert 'include "conan_pkg.name-more+_vars_debug_x86_64.premake5.lua"' in contents
    assert 'include "conan_pkg.name-more+_vars_release_x86_64.premake5.lua"' in contents
    assert 'function conan_setup_build_pkg.name-more+()' in contents
    assert 'function conan_setup_link_pkg.name-more+()' in contents
    assert 'function conan_setup_pkg.name-more+()' in contents

    # Assert package per configuration files
    assert_configuration_file(client, 'debug')
    assert_vars_file(client, 'debug')
    assert_configuration_file(client, 'release')
    assert_vars_file(client, 'release')
