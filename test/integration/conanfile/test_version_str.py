import textwrap

from conan.test.utils.tools import TestClient


def test_conan_version_str():
    """
    conanfile.version should always be a string.
    If comparison neeeded use Version(self.version) or self.ref.version
    """
    # https://github.com/conan-io/conan/issues/10372
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Version

        class Lib(ConanFile):
            name = "pkg"
            version = "1.0"

            def _assert_data(self):
                assert isinstance(self.version, str)
                assert not isinstance(self.version, Version)

            def configure(self):
                self._assert_data()

            def source(self):
                self._assert_data()
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")
