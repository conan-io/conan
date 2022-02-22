import os
import textwrap

from conans.test.utils.tools import TestClient
from conans.util.files import load


def test_autotools_custom_environment():
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import AutotoolsToolchain

            class Conan(ConanFile):
                settings = "os"
                def generate(self):
                    at = AutotoolsToolchain(self)
                    env = at.environment()
                    env.define("FOO", "BAR")
                    at.generate(env)
            """)

    client.save({"conanfile.py": conanfile})
    client.run("install . -sh:os=Linux")
    content = load(os.path.join(client.current_folder,  "conanautotoolstoolchain.sh"))
    assert 'export FOO="BAR"' in content
