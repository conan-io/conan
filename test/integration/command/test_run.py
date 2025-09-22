import textwrap
import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("context", ["host", "build"])
def test_run_basic(context):
    tc = TestClient()
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
            # Make it executable
            os.chmod(os.path.join(self.package_folder, "bin", "myapp.sh"), 0o755)
    """)

    tc.save({"pkg/conanfile.py": conanfile})
    tc.run("create pkg")
    requires = "requires" if context == "host" else "tool-requires"
    tc.run(f"install --{requires}=pkg/0.1")
    tc.run(f"run myapp.sh --context={context}")
    # Commented, find a way to test the output, right now we are not capturing it
    # assert "Hello World!" in tc.out
