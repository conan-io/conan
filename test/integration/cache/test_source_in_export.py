import os
import textwrap

from conan.internal.util import load
from conan.internal.util.files import save_files
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


def test_source_in_export():
    c = TestClient(light=True)
    c.save_home({"global.conf": "core:source_in_export=True"})
    conanfile = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "*.txt"
            def source(self):
                self.output.info(f"Running my SOURCE()!!!: {os.getcwd()}")
                save(self, "myfile.h", "mycontent")
        """)
    c.save({"conanfile.py": conanfile,
            "potato.txt": "some potato"})

    # First we try the local flow, works as usual
    c.run("source")
    assert "Running my SOURCE()!!!" in c.out
    assert "core:source_in_export" not in c.out
    assert "Skipping calling source()" not in c.out
    assert c.load("myfile.h") == "mycontent"
    os.remove(os.path.join(c.current_folder, "myfile.h"))

    # Now the full create flow
    c.run("create")
    assert "Running my SOURCE()!!!" in c.out
    assert "mypkg/1.0: core:source_in_export: Using source() method as export_sources()" in c.out
    assert "mypkg/1.0: Skipping calling source()" in c.out
    layout = c.exported_layout()
    assert load(os.path.join(layout.export_sources(), "myfile.h")) == "mycontent"
    assert load(os.path.join(layout.export_sources(), "potato.txt")) == "some potato"
    manifest = load(os.path.join(layout.export(), "conanmanifest.txt"))
    assert "export_source/.conan_exported_source" in manifest
    assert "export_source/myfile.h" in manifest
    assert "export_source/potato.txt" in manifest

    # we can inhibit changing the conf, keeping regular behavior
    c.run("create -cc core:source_in_export=False")
    assert "Running my SOURCE()!!!" in c.out
    assert "core:source_in_export" not in c.out
    assert "mypkg/1.0: Skipping calling source()" not in c.out
    layout = c.exported_layout()
    assert load(os.path.join(layout.source(), "myfile.h")) == "mycontent"
    assert load(os.path.join(layout.export_sources(), "potato.txt")) == "some potato"
    manifest = load(os.path.join(layout.export(), "conanmanifest.txt"))
    assert "export_source/.conan_exported_source" not in manifest
    assert "export_source/myfile.h" not in manifest
    assert "export_source/potato.txt" in manifest


def test_source_in_export_layout():
    c = TestClient()
    c.save_home({"global.conf": "core:source_in_export=True"})
    conanfile = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "*.txt"
            settings = "os", "arch", "compiler", "build_type"

            def layout(self):
                cmake_layout(self, src_folder="mysrc")

            def source(self):
                self.output.info(f"Running my SOURCE()!!!: {os.getcwd()}")
                save(self, "myfile.h", "mycontent")
        """)
    c.save({"conanfile.py": conanfile,
            "potato.txt": "some potato"})

    # First we try the local flow, works as usual
    c.run("source")
    assert "Running my SOURCE()!!!" in c.out
    assert "core:source_in_export" not in c.out
    assert "Skipping calling source()" not in c.out
    assert c.load("mysrc/myfile.h") == "mycontent"
    os.remove(os.path.join(c.current_folder, "mysrc", "myfile.h"))

    # Now the full create flow
    c.run("create")
    assert "Running my SOURCE()!!!" in c.out
    assert "mypkg/1.0: core:source_in_export: Using source() method as export_sources()" in c.out
    assert "mypkg/1.0: Skipping calling source()" in c.out
    layout = c.exported_layout()
    assert load(os.path.join(layout.export_sources(), "potato.txt")) == "some potato"
    assert load(os.path.join(layout.export_sources(), "mysrc", "myfile.h")) == "mycontent"
    assert load(os.path.join(layout.source(), "potato.txt")) == "some potato"
    assert load(os.path.join(layout.source(), "mysrc", "myfile.h")) == "mycontent"
    manifest = load(os.path.join(layout.export(), "conanmanifest.txt"))
    assert "export_source/.conan_exported_source" in manifest
    assert "export_source/mysrc/myfile.h" in manifest
    assert "export_source/potato.txt" in manifest

    # we can inhibit changing the conf, keeping regular behavior
    c.run("create -cc core:source_in_export=False")
    assert "Running my SOURCE()!!!" in c.out
    assert "core:source_in_export" not in c.out
    assert "mypkg/1.0: Skipping calling source()" not in c.out
    layout = c.exported_layout()
    assert load(os.path.join(layout.source(), "mysrc", "myfile.h")) == "mycontent"
    assert load(os.path.join(layout.export_sources(), "potato.txt")) == "some potato"
    manifest = load(os.path.join(layout.export(), "conanmanifest.txt"))
    assert "export_source/.conan_exported_source" not in manifest
    assert "export_source/mysrc/myfile.h" not in manifest
    assert "export_source/potato.txt" in manifest


def test_source_buildenv():
    c = TestClient()
    c.save_home({"global.conf": "core:source_in_export=True"})
    tool = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import chdir, save

        class Tool(ConanFile):
            name = "tool"
            version = "0.1"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = f"@echo off\necho MY-TOOL! {self.name}/{self.version}!!"
                    save(self, "bin/mytool.bat", echo)
                    save(self, "bin/mytool.sh", echo)
                    os.chmod("bin/mytool.sh", 0o777)
        """)
    c.save({"conanfile.py": tool})
    c.run("create .")

    pkg = textwrap.dedent("""
        from conan import ConanFile
        import platform, os

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            tool_requires = "tool/0.1"

            # IMPORTANT!! Exporting the bat/sh for tool-requires
            exports_sources = "*.bat", "*.sh"

            def source(self):
                cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                self.run(cmd)
        """)
    c.save({"conanfile.py": pkg})

    # As long as we install first the tool-requires and those are exported for source()
    # to execute the tool-requires environment, it works
    c.run("install .")
    c.run("create .")
    assert "MY-TOOL! tool/0.1" in c.out
