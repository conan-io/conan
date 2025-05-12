import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("old_args", [
    "-op=v1 -or=pkg/1.0",
    "-or=pkg/1.0"
])
@pytest.mark.parametrize("new_args", [
    "-np=v2 -nr=pkg/2.0",
    "-nr=pkg/2.0#f42dd964bbf38a73e38e2774579fa634",
])
@pytest.mark.parametrize("formatter", [
    "-f=json --out-file=output.json",
    "-f=html --out-file=output.html"
])
@pytest.mark.tool("git")
def test_compare_paths(old_args, new_args, formatter):
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"v1/conanfile.py": GenConanfile("pkg").with_build_msg("v1"),
            "v2/conanfile.py": GenConanfile("pkg").with_build_msg("v2")})

    tc.run("create v1 --version=1.0")
    v1_path = tc.exported_layout().export()

    tc.run("create v2 --version=2.0")

    tc.run("upload * -r=default -c")
    tc.run("remove * -c")

    tc.run(f'compare {old_args} {new_args} {formatter}')

    if "json" in formatter:
        output_json = json.loads(tc.load("output.json"))
        assert output_json[v1_path + "/conanfile.py"]
        assert output_json[v1_path + "/conanmanifest.txt"]

    elif "html" in formatter:
        output_html = tc.load("output.html")
        assert "(old)/conanfile.py" in output_html
        assert "(old)/conanmanifest.txt" in output_html

