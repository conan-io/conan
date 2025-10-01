import textwrap
import pytest
import platform

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("context", ["host", "build"])
@pytest.mark.parametrize("use_conanfile", [True, False])
def test_run(context, use_conanfile):
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
            save(self, os.path.join(self.package_folder, "bin", "myapp.bat"), "echo Hello World!")
            # Make it executable
            os.chmod(os.path.join(self.package_folder, "bin", "myapp.sh"), 0o755)
            os.chmod(os.path.join(self.package_folder, "bin", "myapp.bat"), 0o755)
    """)

    conanfile_consumer = GenConanfile("consumer", "1.0").with_settings("os")
    if context == "host":
        conanfile_consumer.with_requires("pkg/0.1")
    else:
        conanfile_consumer.with_tool_requires("pkg/0.1")

    tc.save({"pkg/conanfile.py": conanfile, "conanfile.py": conanfile_consumer })
    tc.run("create pkg")
    requires = "requires" if context == "host" else "tool-requires"

    if use_conanfile:
        if platform.system() == "Windows":
            tc.run(f"run myapp.bat --context={context}")
        else:
            tc.run(f"run myapp.sh --context={context}")
    else:
        if platform.system() == "Windows":
            tc.run(f"run myapp.bat --{requires}=pkg/0.1 --context={context}")
        else:
            tc.run(f"run myapp.sh --{requires}=pkg/0.1 --context={context}")
    assert "Hello World!" in tc.out

