import textwrap

from conan.test.utils.tools import GenConanfile, TestClient


def test_add_dep():
    """
    Testing the "conan dep add" command which should always use the highest version
    found in the first remote server or the local cache
    """
    client = TestClient(default_server_user=True)
    # No conanfile is present - error
    client.run("dep add hello", assert_error=True)
    assert "ERROR: Conanfile not found at" in client.out
    client.run("init --ref=app/1.0")  # creates a simple conanfile.py
    # No remote recipe "hello" exists
    client.run("dep add hello")
    assert "ERROR: Recipe hello not found." in client.out
    hello_lib = GenConanfile(name="hello")
    client.save({"hello/conanfile.py": hello_lib})
    client.run("create hello --version=1.0")
    client.run("create hello --version=2.0")
    client.run("create hello --version=3.0")
    client.run("upload * --confirm -r default")
    # Save a normal requires "hello"
    client.run("dep add hello")
    assert "Added 'hello/[^3.0]' as a new requires." in client.out
    content = client.load("conanfile.py")
    assert 'self.requires("hello/[^3.0]")' in content
    # Checking that it works
    client.run("install .")
    expected = textwrap.dedent("""\
    Resolved version ranges
        hello/[^3.0]: hello/3.0
    """)
    assert expected in client.out
    # Try to add it again - does nothing and shows a warning
    client.run("dep add hello")
    assert "The requires hello is already in use."
    # Let's add the same "hello" but now as tool_requires and test_requires
    client.run("dep add hello --tool-requires")  # tool_requires
    assert "Added 'hello/[^3.0]' as a new tool_requires." in client.out
    client.run("dep add hello --tool-requires")
    assert "The requires hello is already in use."
    client.run("dep add hello --test-requires")  # test_requires
    assert "Added 'hello/[^3.0]' as a new test_requires." in client.out
    client.run("dep add hello --test-requires")
    assert "The requires hello is already in use."
    # Using only the local cache
    bye_lib = GenConanfile(name="bye")
    client.save({"bye/conanfile.py": bye_lib})
    client.run("create bye --version=1.0")
    client.run("create bye --version=2.0")
    client.run("dep add bye --no-remote")  # from cache
    assert "Added 'bye/[^2.0]' as a new requires." in client.out


def test_remove_dep():
    client = TestClient(light=True)
    # No conanfile is present - error
    client.run("dep remove hello", assert_error=True)
    assert "ERROR: Conanfile not found at" in client.out
    client.save({"conanfile.py": GenConanfile(name="app")})
    # No requirement "hello" declared
    client.run("dep remove hello")
    assert "WARN: The requirements hello is not declared in your conanfile." in client.out
    client.save({"conanfile.py": GenConanfile(name="app")
                .with_requirement("hello/1.2")
                .with_tool_requirement("hello/1.2")
                .with_test_requirement("hello/1.2")})
    client.run("dep remove hello")  # remove requires
    assert "Removed hello dependency as requires." in client.out
    content = client.load("conanfile.py")
    assert 'self.requires("hello/1.2"' not in content
    assert 'self.tool_requires("hello/1.2"' in content
    assert 'self.test_requires("hello/1.2"' in content
    client.run("dep remove hello --tool-requires")  # remove tool_requires
    content = client.load("conanfile.py")
    assert "Removed hello dependency as tool_requires." in client.out
    assert 'self.tool_requires("hello/1.2"' not in content
    assert 'self.test_requires("hello/1.2"' in content
    client.run("dep remove hello --test-requires")  # remove test_requires
    content = client.load("conanfile.py")
    assert "Removed hello dependency as test_requires." in client.out
    assert 'self.test_requires("hello/1.2"' not in content

    client.run("dep remove hello")
    assert "WARN: The requirements hello is not declared in your conanfile." in client.out
