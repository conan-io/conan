import textwrap


from conans.test.utils.tools import TestClient
from conans.util.files import load, save


FOO_CONANFILE = textwrap.dedent("""
    from conans import ConanFile
    class FooConan(ConanFile):
        settings = ("compiler")
    """)


BAR_CONANFILE = textwrap.dedent("""
    from conans import ConanFile
    class BarConan(ConanFile):
        settings = ("compiler")
        requires = ("foo/1.0")
    """)


# arbitrarily select a compiler; the important thing is that there
# are two different versions used in order to make different package_ids
PROFILE_OLD = textwrap.dedent("""
    [settings]
    compiler=msvc
    compiler.version=170
    compiler.cppstd=17
    compiler.runtime=dynamic
    """)


PROFILE_NEW = textwrap.dedent("""
    [settings]
    compiler=msvc
    compiler.version=180
    compiler.cppstd=17
    compiler.runtime=dynamic
    """)


SPECIFIED_COMPILER_COMPATIBILITY = textwrap.dedent("""
    compiler_compatibility:
        msvc:
            "180": ["170"]
    """)


class TestCompilerCompatible:
    def test_incompatible_dependency(self):
        """
        Build two packages against two profiles with a different compiler version.
        """
        client = TestClient()
        client.save({
            "foo_conanfile.py": FOO_CONANFILE,
            "bar_conanfile.py": BAR_CONANFILE,
            "profile_old": PROFILE_OLD,
            "profile_new": PROFILE_NEW,
        })
        client.run('create foo_conanfile.py foo/1.0@ -pr profile_old')
        # expected failure
        client.run('install bar_conanfile.py bar/2.0@ -pr profile_new', assert_error=True)

    def test_compiler_compatible_dependency(self):
        """
        Build two packages against two profiles with a different compiler version.
        Specify compiler compatibility in the settings.yml
        """
        client = TestClient()

        # Generate the customised settings.yml for compatible compilers for all packages
        client.run("config init")
        default_settings = load(client.cache.settings_path)
        default_settings += SPECIFIED_COMPILER_COMPATIBILITY
        save(client.cache.settings_path, default_settings)

        client.save({
            "foo_conanfile.py": FOO_CONANFILE,
            "bar_conanfile.py": BAR_CONANFILE,
            "profile_old": PROFILE_OLD,
            "profile_new": PROFILE_NEW,
        })
        client.run('create foo_conanfile.py foo/1.0@ -pr profile_old')
        # expected success
        client.run('install bar_conanfile.py bar/2.0@ -pr profile_new', assert_error=False)
        # ensure it is via a compatible package
        assert "Using compatible package" in client.out
