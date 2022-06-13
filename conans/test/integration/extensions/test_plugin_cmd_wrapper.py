import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


def test_plugin_cmd_wrapper():
    c = TestClient()
    plugins = os.path.join(c.cache.cache_folder, "extensions", "plugins")
    wrapper = textwrap.dedent("""
        def cmd_wrapper(cmd):
            return 'echo "{}"'.format(cmd)
        """)
    # TODO: Decide name
    save(os.path.join(plugins, "cmd_wrapper.py"), wrapper)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                self.run("Hello world")
                self.run("Other stuff")
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install .")
    assert 'Hello world' in c.out
    assert 'Other stuff' in c.out


def test_plugin_profile_error_vs():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create . -s compiler=msvc -s compiler.version=15 -s compiler.cppstd=14",
          assert_error=True)
    assert "ERROR: The provided compiler.cppstd=14 requires at least " \
           "msvc>=190 but version 15 provided" in c.out
    c.run("create . -s compiler=msvc -s compiler.version=170 -s compiler.cppstd=14",
          assert_error=True)
    assert "ERROR: The provided compiler.cppstd=14 requires at least " \
           "msvc>=190 but version 170 provided" in c.out
    c.run("create . -s compiler=msvc -s compiler.version=190 -s compiler.cppstd=14")
    assert "Installing packages" in c.out
