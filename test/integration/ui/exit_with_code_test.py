import textwrap

from conan.test.utils.tools import TestClient
from conan.internal.util.files import save


def test_exit_with_code():
    base = textwrap.dedent("""
        import sys
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello0"
            version = "0.1"

            def build(self):
                sys.exit(34)
        """)

    client = TestClient(light=True)
    client.save({"conanfile.py": base})
    client.run("install .")
    error_code = client.run("build .", assert_error=True)
    assert error_code == 34
    assert "Exiting with code: 34" in client.out


def test_wrong_home_error():
    client = TestClient(light=True)
    save(client.paths.new_config_path, "core.cache:storage_path=//")
    client.run("list *")
    assert "Couldn't initialize storage in" in client.out
