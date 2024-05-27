import json

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_build_cmd_deploy_generators():
    """
    Test that "conan build --deployer/--generators" args work
    """
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_settings("build_type")
                                                          .with_requires("dep/1.0")})
    c.run("create dep")
    c.run("build pkg --deployer=full_deploy --deployer-folder=./myfolder -g=CMakeDeps")
    cmake = c.load("pkg/dep-release-data.cmake")
    current_folder = c.current_folder.replace("\\", "/")
    path = f'{current_folder}/myfolder/full_deploy/host/dep/1.0'
    assert f'set(dep_PACKAGE_FOLDER_RELEASE "{path}")' in cmake


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
