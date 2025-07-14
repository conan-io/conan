import json
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_divergent_cppstd_build_host():

    c = TestClient()
    
    conanfile = textwrap.dedent("""
        [requires]
        waterfall/1.0
        [tool_requires]
        rainbow/1.0
        """)

    c.save({"waterfall/conanfile.py": GenConanfile("waterfall", "1.0").with_settings("compiler"),
            "rainbow/conanfile.py": GenConanfile("rainbow", "1.0").with_settings("compiler")
                                                .with_requires("waterfall/1.0"),
            "conanfile.txt": conanfile})


    c.run("export waterfall")
    c.run("export rainbow")
    c.run(f"install . --build=missing -s compiler.cppstd=14 -s:b compiler.cppstd=17 --format=json", redirect_stdout="graph.json")
    graph = json.loads(c.load("graph.json"))


    # waterfall is twice in the graph: as a direct host dependency, and an indirect build dependency
    assert graph['graph']['nodes']['1']['ref'] == "waterfall/1.0#821e924dcef2f185dd651e6d434f9f95"
    assert graph['graph']['nodes']['1']['context'] == "host"

    assert graph['graph']['nodes']['3']['ref'] == "waterfall/1.0#821e924dcef2f185dd651e6d434f9f95"
    assert graph['graph']['nodes']['3']['context'] == "build"

    # is this the right behaviour?
    # without the compatibility plugin, we would require two different package_id in the same graph,
    # but because of compatibility plugin, Conan graph uses a "compatible" package_id in the build context
    # rather than the exact one
    assert graph['graph']['nodes']['1']['package_id'] == graph['graph']['nodes']['3']['package_id']

