import os
import textwrap

from conans.test.utils.tools import TestClient


def test_file_tools():

    conanfile = textwrap.dedent("""

    from conan import ConanFile
    from conan.tools.files import rmdir, mkdir

    class pkg(ConanFile):

        def layout(self):
            self.folders.generators = "gen"

        def generate(self):
            mkdir(self, "folder1")
            mkdir(self, "folder2")
            rmdir(self, "folder2")

    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install . ")
    assert os.path.exists(os.path.join(client.current_folder, "gen", "folder1"))
    assert not os.path.exists(os.path.join(client.current_folder, "gen", "folder2"))
