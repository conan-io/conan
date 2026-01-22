import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("layout", [".", "mysrc"])
def test_source_in_export(layout):
    # This is UNSUPPORTED, it relies on metadata and the default download of SIGN metadata

    c = TestClient(light=True, default_server_user=True)
    subgraph_hook = textwrap.dedent("""\
        import shutil, os, types

        def pre_source(conanfile):
            tgz = os.path.join(conanfile.recipe_metadata_folder, "sign", "backupsrc.tar.gz")
            if os.path.exists(tgz):
                def empty_source(self_):
                    self_.output.info("EMPTY SOURCE!!!")
                shutil.unpack_archive(tgz, conanfile.source_folder)
                conanfile.source = types.MethodType(empty_source, conanfile)

        def post_source(conanfile):
            tgz = os.path.join(conanfile.recipe_metadata_folder, "sign", "backupsrc")
            shutil.make_archive(tgz, "gztar", conanfile.source_folder)
        """)

    c.save_home({"extensions/hooks/source_hook/hook_source.py": subgraph_hook})
    conanfile = textwrap.dedent(f"""\
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"

            def layout(self):
                self.folders.source = "{layout}"

            def source(self):
                self.output.info(f"Running my SOURCE()!!!: {{os.getcwd()}}")
                save(self, "myfile.h", "mycontent")

            def build(self):
                assert os.path.exists(os.path.join(self.source_folder, "myfile.h"))
        """)
    c.save({"conanfile.py": conanfile})

    # First we try the local flow, works as usual
    c.run("source")
    assert "Running my SOURCE()!!!" in c.out
    assert "post_source(): POST SOURCE!!!!"
    assert c.load(f"{layout}/myfile.h") == "mycontent"
    assert os.path.exists(os.path.join(c.current_folder, "metadata", "sign", "backupsrc.tar.gz"))

    # Now the full create flow
    c.run("create")
    assert "Running my SOURCE()!!!" in c.out
    layout = c.exported_layout()
    assert os.path.exists(os.path.join(layout.metadata(), "sign", "backupsrc.tar.gz"))
    c.run("upload * --only-recipe -r=default -c")
    c.run("remove * -c")

    c.run("install --requires=mypkg/1.0 --build=missing")
    assert "Running my SOURCE()!!!" not in c.out
    assert "mypkg/1.0: EMPTY SOURCE!!!" in c.out
