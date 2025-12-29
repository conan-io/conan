import os
import textwrap

from conan.internal.util import load
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
            exports_sources = "*"
            def source(self):
                self.output.info(f"Running my SOURCE()!!!: {os.getcwd()}")
                save(self, "myfile.h", "mycontent")
        """)
    c.save({"conanfile.py": conanfile,
            "potato.txt": "some potato"})
    c.run("create")
    assert "Running my SOURCE()!!!" in c.out
    assert "mypkg/1.0: core:source_in_export: Using source() method as export_sources()" in c.out
    assert "Skipping calling source()" in c.out
    layout = c.exported_layout()
    assert load(os.path.join(layout.export_sources(), "myfile.h")) == "mycontent"
    assert load(os.path.join(layout.export_sources(), "potato.txt")) == "some potato"
