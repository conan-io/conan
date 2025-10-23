import textwrap
import pytest
import platform

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def client():
    tc = TestClient(light=True, default_server_user=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            # So that the requirement is run=True even for --requires
            package_type = "application"

            def package(self):
                save(self, os.path.join(self.package_folder, "bin", "myapp.sh"), "echo Hello World!")
                save(self, os.path.join(self.package_folder, "bin", "myapp.bat"), "echo Hello World!")
                # Make it executable
                os.chmod(os.path.join(self.package_folder, "bin", "myapp.sh"), 0o755)
                os.chmod(os.path.join(self.package_folder, "bin", "myapp.bat"), 0o755)
        """)
    tc.save({"pkg/conanfile.py": conanfile})
    tc.run("create pkg")
    return tc


@pytest.mark.parametrize("context_flag", ["host", "build", None])
@pytest.mark.parametrize("requires_context", ["host", "build",])
@pytest.mark.parametrize("use_conanfile", [True, False])
def test_run(client, context_flag, requires_context, use_conanfile):
    context_arg = {
        "host": "--context=host",
        "build": "--context=build",
        None: "",
    }.get(context_flag)
    should_find_binary = (context_flag == requires_context) or (context_flag is None)
    executable = "myapp.bat" if platform.system() == "Windows" else "myapp.sh"
    if use_conanfile:
        conanfile_consumer = GenConanfile("consumer", "1.0").with_settings("os")
        if requires_context == "host":
            conanfile_consumer.with_requires("pkg/0.1")
        else:
            conanfile_consumer.with_tool_requires("pkg/0.1")

        client.save({"conanfile.py": conanfile_consumer})
        client.run(f"run {executable} {context_arg}", assert_error=not should_find_binary)
    else:
        requires = "requires" if requires_context == "host" else "tool-requires"
        client.run(f"run {executable} --{requires}=pkg/0.1 {context_arg}",
                   assert_error=not should_find_binary)
    if should_find_binary:
        assert "Hello World!" in client.out
    else:
        assert "ERROR" in client.out


def test_run_no_remote_default(client):
    client.run("upload pkg -r=default -c")
    tc = TestClient(servers=client.servers)
    tc.run("list pkg -r=default")

    executable = "myapp.bat" if platform.system() == "Windows" else "myapp.sh"
    tc.run(f"run {executable} --requires=pkg/0.1", assert_error=True)
    assert "ERROR: Package 'pkg/0.1' not resolved: No remote defined" in tc.out

    tc.run(f"run {executable} --requires=pkg/0.1 -r=default")
    assert "Hello World!" in tc.out

    # And it's now in the cache, this should work
    tc.run(f"run {executable} --requires=pkg/0.1")
    assert "Hello World!" in tc.out
