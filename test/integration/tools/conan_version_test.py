import textwrap

from conans.test.utils.tools import TestClient
from conans import __version__


def test_conan_version():

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan import conan_version
        from conan.tools.scm import Version
        from conans import __version__

        class pkg(ConanFile):

            def generate(self):
                assert __version__ == str(conan_version)
                assert isinstance(conan_version, Version)
                print(f"current version: {conan_version}")
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert f"current version: {__version__}" in client.out
