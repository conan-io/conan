import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.xfail(reason="Feature not ready yet")
def test_repackage():
    # consumer -> repackager -> liba (shared)
    #                  \------> libb (static)
    client = TestClient()
    save(client.cache.default_profile_path, "")
    client.save({"conanfile.py": GenConanfile().with_shared_option(True).
                with_settings("os", "arch", "build_type").with_package_file("liba.txt", "HelloA!")})
    client.run("create . --name=liba --version=1.0 -s os=Linux -s arch=x86 -s build_type=RelWithDebInfo")
    client.save({"conanfile.py": GenConanfile().with_shared_option(False).
                with_settings("os", "arch", "build_type").with_package_file("libb.txt", "HelloB!")})
    client.run("create . --name=libb --version=1.0 -s os=Linux -s arch=x86 -s build_type=RelWithDebInfo")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"

            def requirements(self):
                self.requires("liba/1.0", headers=True, libs=True, visible=False, run=False)
                self.requires("libb/1.0", headers=True, libs=True, visible=False, run=False)

            def generate(self):
                pass

            def package(self):
                # copy things
                pass

            def package_info(self):
                pass
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=repackager --version=1.0 -s os=Linux -s arch=x86 -s build_type=RelWithDebInfo")

    client.save({"conanfile.py": GenConanfile().with_requires("repackager/1.0")}, clean_first=True)
    client.run("install . -s os=Linux")
    assert "liba/1.0:INVALID - Skip" in client.out
    assert "libb/1.0:INVALID - Skip" in client.out
    assert "repackager/1.0: Already installed!" in client.out


