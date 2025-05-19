import json
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("old_args", [
    "-op=v1 -or=pkg/1.0",
    "-or=pkg/1.0"
])
@pytest.mark.parametrize("new_args", [
    "-np=v2 -nr=pkg/2.0",
    "-nr=pkg/2.0#16fad934f9a90b1da6740cbac9590b53",
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
            apply_conandata_patches(self)
    """)

    tc.save({
        "v1/conanfile.py": conanfile.format(version="v1"),
        "v1/conandata.yml": conandata_yml.format(version="1.0"),
        "v1/1.0.txt": "1.0",
        "v1/patches/patch.patch": patch_file.format(version="1.0"),

        "v2/conanfile.py": conanfile.format(version="v2"),
        "v2/conandata.yml": conandata_yml.format(version="2.0"),
        "v2/2.0.txt": "2.0",
        "v2/patches/patch.patch": patch_file.format(version="2.0"),
    })

    tc.run("create v1 --version=1.0")
    v1_path = tc.exported_layout().export()

    tc.run("create v2 --version=2.0")

    tc.run("upload * -r=default -c")
    tc.run("remove * -c")

    tc.run(f'compare {old_args} {new_args} {formatter}')

    if "json" in formatter:
        output_json = json.loads(tc.load("output.json"))
        assert output_json[os.path.join(v1_path, "conanfile.py")]
        assert output_json[os.path.join(v1_path, "conanmanifest.txt")]

    elif "html" in formatter:
        output_html = tc.load("output.html")
        assert """<span class="context">--- a(pkg/1.0#147b6df93bdb64119aa4208cb4825184)/es/patches/patch.patch	</span>""" in output_html

