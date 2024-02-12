import json
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_build_output_json():
    """
    The build command should have the --format=json option.
    """
    _OUTPUT_FILE = "output.json"

    client = TestClient()
    conanfile = GenConanfile()
    client.save({"conanfile.py": conanfile})
    client.run("build . --format=json", redirect_stdout=_OUTPUT_FILE)
    output = json.loads(client.load(_OUTPUT_FILE))

    assert "graph" in output
    assert "nodes" in output["graph"]
