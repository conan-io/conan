import textwrap

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
