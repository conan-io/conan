import textwrap
import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save
import os

# Using the sbom tool with "conan create"
sbom_hook_post_package = """
import json
import os
from conan.errors import ConanException
from conan.api.output import ConanOutput
from conan.tools.sbom import cyclonedx_1_4

def post_package(conanfile):
    sbom_cyclonedx_1_4 = cyclonedx_1_4(conanfile, add_build=%s, add_tests=%s)
    metadata_folder = conanfile.package_metadata_folder
    file_name = "sbom.cdx.json"
    with open(os.path.join(metadata_folder, file_name), 'w') as f:
        json.dump(sbom_cyclonedx_1_4, f, indent=4)
    ConanOutput().success(f"CYCLONEDX CREATED - {conanfile.package_metadata_folder}")
"""

@pytest.fixture()
def hook_setup_post_package_default():
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_package % ("False", "False"))
    return tc

@pytest.fixture()
def hook_setup_post_package():
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_package % ("True", "True"))
    return tc


@pytest.fixture()
def hook_setup_post_package_no_tool_requires():
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_package % ("False", "True"))
    return tc


@pytest.fixture()
def hook_setup_post_package_no_test():
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_package % ("True", "False"))
    return tc


@pytest.fixture()
def hook_setup_post_package_tl(transitive_libraries):
    tc = transitive_libraries
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_package % ("True", "True"))
    return tc


def test_sbom_generation_create(hook_setup_post_package_tl):
    tc = hook_setup_post_package_tl
    tc.run("new cmake_lib -d name=bar -d version=1.0 -d requires=engine/1.0 -f")
    # bar -> engine/1.0 -> matrix/1.0
    tc.run("create . -tf=")
    bar_layout = tc.created_layout()
    assert os.path.exists(os.path.join(bar_layout.metadata(), "sbom.cdx.json"))


def test_sbom_generation_skipped_dependencies(hook_setup_post_package):
    tc = hook_setup_post_package
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
             "app/conanfile.py": GenConanfile("app", "1.0")
                                .with_package_type("application")
                                .with_requires("dep/1.0"),
             "conanfile.py": GenConanfile("foo", "1.0").with_tool_requires("app/1.0")})
    tc.run("create dep")
    tc.run("create app")
    tc.run("create .")
    create_layout = tc.created_layout()

    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = tc.load(cyclone_path)
    # A skipped dependency also shows up in the sbom
    assert "pkg:conan/dep@1.0?rref=6a99f55e933fb6feeb96df134c33af44" in content

@pytest.mark.parametrize("l, n", [('"simple"', 1), ('"multi1", "multi2"', 2), ('("tuple1", "tuple2")', 2)])
def test_multi_license(hook_setup_post_package, l, n):
    tc = hook_setup_post_package
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class HelloConan(ConanFile):
            name = 'foo'
            version = '1.0'
            license = %s
    """)
    tc.save({"conanfile.py": conanfile % l})
    tc.run("create .")
    create_layout = tc.created_layout()
    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = json.loads(tc.load(cyclone_path))
    assert len(content["components"][0]["licenses"]) == n

def test_sbom_generation_no_tool_requires(hook_setup_post_package_no_tool_requires):
    tc = hook_setup_post_package_no_tool_requires
    tc.save({"app/conanfile.py": GenConanfile("app", "1.0")
                                .with_package_type("application"),
             "conanfile.py": GenConanfile("foo", "1.0").with_tool_requires("app/1.0")})
    tc.run("create app")
    tc.run("create .")
    create_layout = tc.created_layout()

    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = tc.load(cyclone_path)

    assert "pkg:conan/app" not in content


def test_sbom_generation_transitive_test_requires(hook_setup_post_package_no_test):
    tc = hook_setup_post_package_no_test
    tc.save({"test_re/conanfile.py": GenConanfile("test_re", "1.0"),
             "app/conanfile.py": GenConanfile("app", "1.0")
                                .with_package_type("application")
                                .with_test_requires("test_re/1.0"),
             "conanfile.py": GenConanfile("foo", "1.0").with_tool_requires("app/1.0")})
    tc.run("create test_re")

    tc.run("create app")
    create_layout = tc.created_layout()
    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = tc.load(cyclone_path)
    assert "pkg:conan/test_re@1.0" not in content

    tc.run("create .")
    create_layout = tc.created_layout()
    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = tc.load(cyclone_path)
    assert "pkg:conan/test_re@1.0" not in content


def test_sbom_generation_dependency_test_require(hook_setup_post_package_no_test):
    tc = hook_setup_post_package_no_test
    tc.save({"special/conanfile.py": GenConanfile("special", "1.0"),
             "foo/conanfile.py": GenConanfile("foo", "1.0")
            .with_test_requires("special/1.0"),
             "conanfile.py": GenConanfile("bar", "1.0").with_tool_requires("foo/1.0").with_require("special/1.0")})
    tc.run("create special")
    tc.run("create foo")

    tc.run("create .")
    create_layout = tc.created_layout()
    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = tc.load(cyclone_path)
    assert "pkg:conan/special@1.0" in content


# Using the sbom tool with "conan install"
sbom_hook_post_generate = """
import json
import os
from conan.errors import ConanException
from conan.api.output import ConanOutput
from conan.tools.sbom import cyclonedx_1_4

def post_generate(conanfile):
    sbom_cyclonedx_1_4 = cyclonedx_1_4(conanfile, name=%s)
    generators_folder = conanfile.generators_folder
    file_name = "sbom.cdx.json"
    os.mkdir(os.path.join(generators_folder, "sbom"))
    with open(os.path.join(generators_folder, "sbom", file_name), 'w') as f:
        json.dump(sbom_cyclonedx_1_4, f, indent=4)
    ConanOutput().success(f"CYCLONEDX CREATED - {conanfile.generators_folder}")
"""


@pytest.fixture()
def hook_setup_post_generate():
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_generate % "None")
    return tc


def test_sbom_generation_install_requires(hook_setup_post_generate):
    tc = hook_setup_post_generate
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
             "conanfile.py": GenConanfile("foo", "1.0").with_requires("dep/1.0")})
    tc.run("export dep")
    tc.run("create . --build=missing")

    # cli -> foo -> dep
    tc.run("install --requires=foo/1.0")
    assert os.path.exists(os.path.join(tc.current_folder, "sbom", "sbom.cdx.json"))


def test_sbom_generation_install_path(hook_setup_post_generate):
    tc = hook_setup_post_generate
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
             "conanfile.py": GenConanfile("foo", "1.0").with_requires("dep/1.0")})
    tc.run("create dep")

    # foo -> dep
    tc.run("install .")
    assert os.path.exists(os.path.join(tc.current_folder, "sbom", "sbom.cdx.json"))


def test_sbom_generation_install_path_consumer(hook_setup_post_generate):
    tc = hook_setup_post_generate
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
             "conanfile.py": GenConanfile().with_requires("dep/1.0")})
    tc.run("create dep")

    # conanfile.py -> dep
    tc.run("install .")
    assert os.path.exists(os.path.join(tc.current_folder, "sbom", "sbom.cdx.json"))


def test_sbom_generation_install_path_txt(hook_setup_post_generate):
    tc = hook_setup_post_generate
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
             "conanfile.txt": textwrap.dedent(
                 """
                 [requires]
                 dep/1.0
                 """
             )})
    tc.run("create dep")

    # foo -> dep
    tc.run("install .")
    assert os.path.exists(os.path.join(tc.current_folder, "sbom", "sbom.cdx.json"))

def test_sbom_with_special_root_node(hook_setup_post_generate):
    # In this test, we have only one node in the subgraph, which has build context, so the number
    # of components after processing it is zero.
    tc = hook_setup_post_generate
    package_name = "foo"

    conanfile =  textwrap.dedent("""
            from conan import ConanFile
            class FooPackage(ConanFile):
                name = "foo"
                version = "1.0"
                package_type = "build-scripts"
    """)
    tc.save({"conanfile.py": conanfile})
    tc.run("create .")
    create_layout = tc.created_layout()
    assert os.path.exists(os.path.join(create_layout.build(), "sbom", "sbom.cdx.json"))
    with open(os.path.join(create_layout.build(), "sbom", "sbom.cdx.json"), 'r') as file:
        sbom_json = json.load(file)
        assert package_name in sbom_json["metadata"]["component"]["name"]

@pytest.mark.parametrize("name, result", [
    ("None", "conan-sbom"),
    ('"custom-name"', "custom-name")
])
def test_sbom_generation_custom_name(name, result):
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, sbom_hook_post_generate % name)

    tc.save({"conanfile.py": GenConanfile()})
    tc.run("install .")
    assert os.path.exists(os.path.join(tc.current_folder, "sbom", "sbom.cdx.json"))
    assert f'"name": "{result}"' in tc.load(os.path.join(tc.current_folder, "sbom", "sbom.cdx.json"))

@pytest.mark.parametrize("cyclone_version", ["cyclonedx_1_4", "cyclonedx_1_6"])
def test_cyclonedx_check_content(cyclone_version):
    _sbom_hook_post_package = textwrap.dedent("""
    import json
    import os
    from conan.errors import ConanException
    from conan.api.output import ConanOutput
    from conan.tools.sbom import %s

    def post_package(conanfile):
        sbom_cyclonedx= %s(conanfile)
        metadata_folder = conanfile.package_metadata_folder
        file_name = "sbom.cdx.json"
        with open(os.path.join(metadata_folder, file_name), 'w') as f:
            json.dump(sbom_cyclonedx, f, indent=4)
        ConanOutput().success(f"CYCLONEDX CREATED - {conanfile.package_metadata_folder}")
    """)
    tc = TestClient()
    hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
    save(hook_path, _sbom_hook_post_package % (cyclone_version, cyclone_version))
    conanfile_bar = textwrap.dedent("""
            from conan import ConanFile
            class HelloConan(ConanFile):
                name = 'bar'
                version = '1.0'
                author = 'conan-dev'
                package_type = 'application'
        """)

    conanfile_foo = textwrap.dedent("""
        from conan import ConanFile
        class HelloConan(ConanFile):
            name = 'foo'
            version = '1.0'
            author = 'conan-dev'
            package_type = 'application'

            def requirements(self):
                self.requires("bar/1.0")
    """)
    tc.save({"conanfile.py": conanfile_bar})
    tc.run("create .")
    tc.save({"conanfile.py": conanfile_foo})
    tc.run("create .")

    create_layout = tc.created_layout()
    cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
    content = tc.load(cyclone_path)
    content_json = json.loads(content)
    if cyclone_version == 'cyclonedx_1_4':
        assert content_json["metadata"]["component"]["author"] == 'conan-dev'
        assert content_json["metadata"]["component"]["type"] == 'application'
        assert content_json["metadata"]["tools"][0]
        assert content_json["components"][0]["author"] == 'conan-dev'
        assert content_json["components"][0]["type"] == 'application'
    elif cyclone_version == 'cyclonedx_1_6':
        assert not content_json["metadata"]["component"].get("author")
        assert content_json["metadata"]["component"]["authors"][0]["name"] == 'conan-dev'
        assert content_json["metadata"]["component"]["type"] == 'application'
        assert content_json["metadata"]["tools"]["components"][0]
        assert not content_json["components"][0].get("author")
        assert content_json["components"][0]["authors"][0]["name"] == 'conan-dev'
        assert content_json["components"][0]["type"] == 'application'
