import textwrap

from conan.test.utils.tools import TestClient


def test_workspace_add_ref_parses_and_persists():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
    """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=company")
    client.run("workspace init .")
    client.run("workspace add --ref=mypkg/1.0@company")
    client.run("workspace info")
    assert "mypkg/1.0@company" in client.out


def test_workspace_add_ref_rejects_individual_reference_arguments():
    client = TestClient()
    client.run("workspace init .")
    client.run(
        "workspace add --ref=mypkg/1.0@company --version=2.0",
        assert_error=True
    )
    assert "Do not use '--ref' together with '--name', '--version', " \
           "'--user' or '--channel' arguments" in client.out


def test_workspace_add_ref_rejects_invalid_reference():
    client = TestClient()
    client.run("workspace init .")
    client.run("workspace add --ref=invalid-format", assert_error=True)
    assert "not a valid recipe reference" in client.out
