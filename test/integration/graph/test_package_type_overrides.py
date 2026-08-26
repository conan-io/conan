import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


liba = textwrap.dedent("""\
    import os
    from conan import ConanFile
    from conan.tools.files import save

    class LibA(ConanFile):
        name = "liba"
        version = "0.1"
        package_type = "static-library"
        package_type_inferring = {package_type_inferring}

        def package(self):
            # This static-library also ships a shared library, faked here with a script, that
            # consumers link, and that has to be found at runtime
            save(self, os.path.join(self.package_folder, "lib", "liba.a"), "fake static lib")
            save(self, os.path.join(self.package_folder, "bin", "myshared.bat"),
                 "@echo off\\necho MYSHARED RUNTIME!!")
            sh = os.path.join(self.package_folder, "bin", "myshared.sh")
            save(self, sh, "echo MYSHARED RUNTIME!!")
            os.chmod(sh, 0o777)
    """)

app = textwrap.dedent("""\
    import platform
    from conan import ConanFile

    class App(ConanFile):
        settings = "os"  # Necessary, or the "conanrun" env would be a .sh script in Windows
        requires = "{requires}"

        def build(self):
            cmd = "myshared.bat" if platform.system() == "Windows" else "myshared.sh"
            self.run(cmd, env="conanrun")
    """)


def _not_found(out):
    """ the shell couldn't find our script, that is, it was not in the PATH of the run
    environment: 'not recognized' in cmd, 'not found' in sh (with or without 'command')
    """
    return re.search(r"myshared\.(bat|sh).*(not recognized|not found)", out)


@pytest.mark.parametrize("package_type_inferring", [True, False])
def test_package_type_inferring_run_trait(package_type_inferring):
    """ a package_type=static-library that also contains a shared library, which the consumer
    has to find at runtime, so its location must be in the "conanrun" environment
    """
    c = TestClient(light=True)
    c.save({"liba/conanfile.py": liba.format(package_type_inferring=f"{{ 'run': {package_type_inferring} }}"),
            "app/conanfile.py": app.format(requires="liba/0.1")})
    c.run("create liba")

    c.run("build app", assert_error=not package_type_inferring)
    if package_type_inferring:
        assert "MYSHARED RUNTIME!!" in c.out
    else:
        # Without "package_type_inferring" the run trait is False, as it is a static-library, so the
        # "bindirs" of liba are not added to the "conanrun" environment
        assert "MYSHARED RUNTIME!!" not in c.out
        assert _not_found(c.out)
        assert "Error in build() method" in c.out


@pytest.mark.parametrize("package_type_inferring", [True, False])
def test_package_type_inferring_run_transitive(package_type_inferring):
    """ app -> libb (shared-library) -> liba (static-library shipping a shared library)
    The libs of liba are linked inside libb, so app doesn't need them, but the shared library
    that liba ships still has to be there at runtime, so its binary cannot be skipped
    """
    c = TestClient(light=True)
    c.save({"liba/conanfile.py": liba.format(package_type_inferring=f"{{ 'run': {package_type_inferring} }}"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_package_type("shared-library")
                                                            .with_requires("liba/0.1"),
            "app/conanfile.py": app.format(requires="libb/0.1")})
    c.run("create liba")
    c.run("create libb")

    c.run("build app", assert_error=not package_type_inferring)
    if package_type_inferring:
        # The liba binary is necessary at runtime, so it cannot be skipped
        assert "Skipped binaries" not in c.out
        assert "MYSHARED RUNTIME!!" in c.out
    else:
        # Without "package_type_inferring" the run trait is False, and as liba is a static-library
        # linked inside libb, Conan understands its binary is not necessary anymore and skips it
        assert re.search(r"Skipped binaries(\s*)liba/0.1", c.out)
        assert "MYSHARED RUNTIME!!" not in c.out
        assert _not_found(c.out)
        assert "Error in build() method" in c.out
