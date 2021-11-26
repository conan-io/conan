import os
import textwrap

from conans.test.utils.tools import TestClient


def test_premakedeps():
    conanfile = textwrap.dedent("""
        [generators]
        PremakeDeps
        """)
    client = TestClient()
    client.save({"conanfile.txt": conanfile}, clean_first=True)
    client.run("install .")

    assert os.path.exists(os.path.join(client.current_folder, "conanbuildinfo.premake.lua"))
    contents = client.load("conanbuildinfo.premake.lua")
    assert 'function conan_basic_setup()' in contents
