import textwrap

from conan.test.utils.tools import GenConanfile, TestClient


def test_add_require():
    """
    Testing the "conan dep add" command which should always use the highest version
    found in the first remote server or the local cache
    """
    client = TestClient(default_server_user=True, light=True)
    # No conanfile is present - error
    client.run("require add hello", assert_error=True)
    assert "ERROR: Conanfile not found at" in client.out
    client.save({"conanfile.py": GenConanfile(name="app")})
    # No requirements define
    client.run("require add", assert_error=True)
    assert "ERROR: You need to add any requires, tool_requires or test_requires." in client.out
    # No remote recipe "hello" exists
    client.run("require add hello")
    assert "ERROR: Recipe hello not found." in client.out
    hello_lib = GenConanfile(name="hello")
    client.save({"hello/conanfile.py": hello_lib})
    client.run("create hello --version=1.0")
    client.run("create hello --version=2.0")
    client.run("create hello --version=3.0")
    client.run("upload * --confirm -r default")
    # Save a normal requires "hello"
    client.run("require add hello")
    assert "Added 'hello/[>=3.0 <4]' as a new requires." in client.out
    content = client.load("conanfile.py")
    assert 'self.requires("hello/[>=3.0 <4]")' in content
    # Checking that it works
    client.run("install .")
    expected = textwrap.dedent("""\
    Resolved version ranges
        hello/[>=3.0 <4]: hello/3.0
    """)
    assert expected in client.out
    # Let's add the same "hello" but now as tool_requires and test_requires
    client.run("require add --tool=hello --test=hello")  # [tool|test]_requires
    assert "Added 'hello/[>=3.0 <4]' as a new tool_requires." in client.out
    assert "Added 'hello/[>=3.0 <4]' as a new test_requires." in client.out
    # Try to add them again - does nothing and shows a warning
    client.run("require add hello --tool=hello --test=hello")
    assert "The requires hello is already in use." in client.out
    assert "The tool_requires hello is already in use." in client.out
    assert "The test_requires hello is already in use." in client.out

    # Using only the local cache
    bye_lib = GenConanfile(name="bye")
    client.save({"bye/conanfile.py": bye_lib})
    client.run("create bye --version=1.0")
    client.run("create bye --version=2.0")
    client.run("require add bye --no-remote")  # from cache
    assert "Added 'bye/[>=2.0 <3]' as a new requires." in client.out

    # Using a specific version (it does not look for it neither locally nor remotely)
    client.run("require add mylib/1.2")
    assert "Added 'mylib/[>=1.2 <2]' as a new requires." in client.out

    # Using commit as a version
    client.run("require add other/cci.20203034")  # can not bump the version, won't use vrange
    assert "Added 'other/cci.20203034' as a new requires." in client.out


def test_remove_require():
    client = TestClient(light=True)
    # No conanfile is present - error
    client.run("require remove hello", assert_error=True)
    assert "ERROR: Conanfile not found at" in client.out
    client.save({"conanfile.py": GenConanfile(name="app")})
    # No requirement "hello" declared
    client.run("require remove hello")
    assert "WARN: The requires hello is not declared in your conanfile." in client.out
    client.save({"conanfile.py": GenConanfile(name="app")
                .with_requirement("hello/1.2")
                .with_tool_requirement("hello/1.2")
                .with_test_requirement("hello/1.2")})
    client.run("require remove hello --tool=hello --test=hello")
    assert "Removed hello dependency as requires." in client.out
    assert "Removed hello dependency as tool_requires." in client.out
    assert "Removed hello dependency as test_requires." in client.out
    content = client.load("conanfile.py")
    assert 'self.requires("hello/1.2"' not in content
    assert 'self.tool_requires("hello/1.2"' not in content
    assert 'self.test_requires("hello/1.2"' not in content
    client.run("require remove hello --tool=hello --test=hello")
    assert "WARN: The requires hello is not declared in your conanfile." in client.out
    assert "WARN: The tool_requires hello is not declared in your conanfile." in client.out
    assert "WARN: The test_requires hello is not declared in your conanfile." in client.out
