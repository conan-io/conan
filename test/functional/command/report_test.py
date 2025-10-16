import json
import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("old_args", [
    "-op=v1 -or=pkg/1.0",
    "-or=pkg/1.0"
])
@pytest.mark.parametrize("new_args", [
    "-np=v2 -nr=pkg/2.0",
    "-nr=pkg/2.0#{revision}",
])
@pytest.mark.parametrize("formatter", [
    "-f=json --out-file=output.json",
    "-f=html --out-file=output.html"
])
@pytest.mark.tool("git")
def test_compare_paths(old_args, new_args, formatter):
    tc = TestClient(light=True, default_server_user=True)

    patch_file = textwrap.dedent("""
    diff --git a/foo.txt b/foo.txt
    new file mode 100644
    index 0000000..e311fbb
    --- /dev/null
    +++ b/foo.txt
    @@ -0,0 +1 @@
    +{version}
    """)

    conandata_yml = textwrap.dedent("""
    patches:
      "{version}":
        - patch_file: "patches/patch.patch"
    """)

    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.files import apply_conandata_patches, export_conandata_patches, save

    class TestConan(ConanFile):
        name = "pkg"

        exports = "{version}.txt"

        def export_sources(self):
            export_conandata_patches(self)

        def source(self):
            save(self, "myfile.txt", "{version}")
            if self.version == "2.0":
                save(self, "new-file-for-v2.txt", "a new file for the new version")
            apply_conandata_patches(self)
    """)

    tc.save({
        "v1/conanfile.py": conanfile.format(version="v1"),
        "v1/conandata.yml": conandata_yml.format(version="1.0"),
        "v1/v1.txt": "1.0",
        "v1/patches/patch.patch": patch_file.format(version="1.0"),

        "v2/conanfile.py": conanfile.format(version="v2"),
        "v2/conandata.yml": conandata_yml.format(version="2.0"),
        "v2/v2.txt": "2.0",
        "v2/patches/patch.patch": patch_file.format(version="2.0"),
    })

    tc.run("create v1 --version=1.0")
    v1_layout = tc.exported_layout()
    v1_path = v1_layout.export()

    tc.run("create v2 --version=2.0")
    v2_revision = tc.exported_layout().reference.revision

    tc.run("upload * -r=default -c")
    tc.run("remove * -c")

    new_args = new_args.format(revision=v2_revision)

    tc.run(f'report diff {old_args} {new_args} {formatter}')

    if "json" in formatter:
        output_json = json.loads(tc.load("output.json"))
        assert any(os.path.join(v1_path, "conanfile.py").replace("\\", "/") in k for k in output_json.keys())
        assert any(os.path.join(v1_path, "conanmanifest.txt").replace("\\", "/") in k for k in output_json.keys())
        # We have patch information
        assert any(os.path.abspath(os.path.join(v1_path, "..", "es", "patches", "patch.patch")).replace("\\", "/") in k for k in output_json.keys())
        # '/private/var/folders/lw/6bflvp3s3t5b56n2p_bj_vx80000gn/T/tmptcto18wfconans/path with spaces/.conan2/p/pkg8fd97e4b9cf55/es/patches/patch.patch'
        # We have exports information
        assert any(os.path.abspath(os.path.join(v1_path, "..", "e", "v1.txt")).replace("\\", "/") in k for k in output_json.keys())
        # New files
        assert any("new-file-for-v2.txt" in k for k in output_json.keys())

    elif "html" in formatter:
        output_html = tc.load("output.html")
        # We have patch information
        assert f"""(new)/es/patches/patch.patch""" in output_html
        # We have exports information
        assert f"""(old)/e/v1.txt""" in output_html
        # New files appear both in the menu and in the diff
        assert output_html.count("(new)/s/new-file-for-v2.txt") == 3

