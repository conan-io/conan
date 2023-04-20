import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_deployer_custom_version_output():
    deployer = textwrap.dedent("""
    import os
    def deploy(graph, output_folder, **kwargs):
        # When running graph info with --requires, the root of the graph is a virtual node, skip it
        if graph.root.recipe == "Cli":
            ref_version = str(graph.nodes[1].ref)
        else:
            ref_version = str(graph.root.ref)
        # ref_version is of the form name/version{@user/channel}
        # More granular control is possible by accessing ref.name, ref.version etc
        output_folder = os.path.join(output_folder, "deployed", str(ref_version))
        print(f"{output_folder} : OUTPUT")
        """)
    tc = TestClient()
    tc.save({"mydeploy.py": deployer, "conanfile.py": GenConanfile("pkg", "1.0")})
    tc.run("create .")
    tc.run("graph info --require=pkg/1.0 --deploy=mydeploy")
    assert "/deployed/pkg/1.0 : OUTPUT" in tc.out

    tc.save({"conanfile.py": GenConanfile("other", "2.5")})
    tc.run("graph info . --deploy=mydeploy")
    assert "/deployed/other/2.5" in tc.out
