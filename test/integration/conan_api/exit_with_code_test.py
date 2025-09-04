import textwrap

from conan.test.utils.tools import TestClient


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
