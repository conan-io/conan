import json
import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import load


def test_subgraph_reports():
    c = TestClient()
    subgraph_hook = textwrap.dedent("""\
        import os, json
        from conan.tools.files import save
        from conans.model.graph_lock import Lockfile

        def post_package(conanfile):
            subgraph = conanfile.subgraph

            save(conanfile, os.path.join(conanfile.package_folder, "conangraph.json"),
                 json.dumps(subgraph.serialize(), indent=2))
            save(conanfile, os.path.join(conanfile.package_folder, "conan.lock"),
                 Lockfile(subgraph).dumps())
        """)

    c.save_home({"extensions/hooks/subgraph_hook/hook_subgraph.py": subgraph_hook})
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requirement("dep/0.1"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requirement("pkg/0.1")})
    c.run("export dep")
    c.run("export pkg")
    c.run("create app --build=missing --format=json")

    graph = json.loads(c.stdout)
    folder = graph["graph"]["nodes"]["2"]["package_folder"]
    graph = load(os.path.join(folder, "conangraph.json"))
    print(graph)
    lock = load(os.path.join(folder, "conan.lock"))
    print(lock)

    # Save it in metadata files? => extensible for future manifests
