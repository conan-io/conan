import textwrap

from conan.test.utils.tools import TestClient, GenConanfile


class TestLoopDetection:

    def test_transitive_loop(self):
        client = TestClient(light=True)
        client.save({
            'pkg1.py': GenConanfile().with_require('pkg2/0.1@lasote/stable'),
            'pkg2.py': GenConanfile().with_require('pkg3/0.1@lasote/stable'),
            'pkg3.py': GenConanfile().with_require('pkg1/0.1@lasote/stable'),
        })
        client.run('export pkg1.py --name=pkg1 --version=0.1 --user=lasote --channel=stable')
        client.run('export pkg2.py --name=pkg2 --version=0.1 --user=lasote --channel=stable')
        client.run('export pkg3.py --name=pkg3 --version=0.1 --user=lasote --channel=stable')

        client.run("install --requires=pkg3/0.1@lasote/stable --build='*'", assert_error=True)
        # TODO: Complete with better diagnostics
        assert "ERROR: There is a cycle/loop in the graph" in client.out

    def test_self_loop(self):
        client = TestClient(light=True)
        client.save({'pkg1.py': GenConanfile().with_require('pkg1/0.1@lasote/stable'), })
        client.run('export pkg1.py --name=pkg1 --version=0.1 --user=lasote --channel=stable')
        client.run("install --requires=pkg1/0.1@lasote/stable --build='*'", assert_error=True)
        assert "ERROR: There is a cycle/loop in the graph" in client.out


def test_install_order_infinite_loop():
    c = TestClient(light=True)
    c.save({"fmt/conanfile.py": GenConanfile("fmt", "1.0"),
            "tool/conanfile.py": GenConanfile("tool", "1.0").with_requires("fmt/1.0"),
            "tool_profile": "[tool_requires]\n!tool/*: tool/1.0"})
    c.run("export fmt")
    c.run("export tool")
    c.run("install tool -pr:h=tool_profile -b=missing",
          assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    assert "fmt/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709 (Build) -> " \
           "['tool/1.0:044d18636d2b7da86d3aa46a2aabf1400db525b1']" in c.out
    assert "tool/1.0:044d18636d2b7da86d3aa46a2aabf1400db525b1 (Build) -> " \
           "['fmt/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709']" in c.out

    # Graph build-order fails in the same way
    c.run("graph build-order tool -pr:h=tool_profile -b=missing --order-by=recipe",
          assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    assert "fmt/1.0 (Build) -> ['tool/1.0']" in c.out
    assert "tool/1.0 (Build) -> ['fmt/1.0']" in c.out

    c.run("graph build-order tool -pr:h=tool_profile --order-by=configuration -b=missing",
          assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    assert "fmt/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709 (Build) -> " \
           "['tool/1.0:044d18636d2b7da86d3aa46a2aabf1400db525b1']" in c.out
    assert "tool/1.0:044d18636d2b7da86d3aa46a2aabf1400db525b1 (Build) -> " \
           "['fmt/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709']" in c.out


def _compiler_bootstrap_client(host_compiler_version):
    c = TestClient()
    c.save({
        "clang-bootstrap/conanfile.py": GenConanfile("clang-bootstrap", "1.0")
        .with_package_type("application").with_settings("os", "arch")
        .with_build_msg("BUILD BOOTSTRAP"),
        "clang-hybrid/conanfile.py": GenConanfile("clang-hybrid", "1.0")
        .with_package_type("application").with_settings("os", "arch", "compiler", "build_type")
        .with_requires("z3/1.0")
        .with_build_msg("BUILD HYBRID"),
        "z3/conanfile.py": GenConanfile("z3", "1.0")
        .with_package_type("static-library").with_settings("os", "arch", "compiler", "build_type")
        .with_build_msg("BUILD Z3"),
        "app/conanfile.txt": "[requires]\nz3/1.0",
        "profile_build": "[settings]\nos=Linux\narch=x86_64\ncompiler=clang\n"
                         "compiler.version=21\ncompiler.libcxx=libstdc++11\nbuild_type=Release\n\n"
                         "[tool_requires]\n"
                         "!clang-bootstrap/*: clang-bootstrap/1.0",
        "profile_host": "[settings]\nos=Linux\narch=x86_64\ncompiler=clang\n"
                        f"compiler.version={host_compiler_version}\n"
                        "compiler.libcxx=libstdc++11\nbuild_type=Release\n\n"
                        "[tool_requires]\n*: clang-hybrid/1.0"
    })
    c.run("export clang-bootstrap")
    c.run("export z3")
    c.run("export clang-hybrid")
    return c


def test_install_order_recipe_cycle_from_distinct_configurations():
    c = _compiler_bootstrap_client("22")

    args = "app -pr:b=profile_build -pr:h=profile_host --build=missing -nr"
    c.run(f"graph info {args}")
    c.run(f"install {args}")
    bootstrap = c.out.index("BUILD BOOTSTRAP")
    first_z3 = c.out.index("BUILD Z3")
    hybrid = c.out.index("BUILD HYBRID")
    second_z3 = c.out.rindex("BUILD Z3")
    assert bootstrap < first_z3 < hybrid < second_z3


def test_install_order_cycle_from_same_configuration():
    c = _compiler_bootstrap_client("21")
    args = "app -pr:b=profile_build -pr:h=profile_host --build=missing -nr"
    c.run(f"graph info {args}", assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    c.run(f"install {args}", assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out


def test_build_require_undetected_loop():
    c = TestClient(light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class DemoRecipe(ConanFile):
            name = "test"
            version = "1.0"

            def requirements(self):
                self.requires("cmake/3.31.6", build=True)

            def build_requirements(self):
                self.tool_requires("cmake/3.31.6", options={
                    "bad": True # this doesn't need to be a valid option
                })

            def generate(self):
                self.output.info(f"NUM DEPS: {len(self.dependencies.items())}")
        """)
    c.save({"cmake/conanfile.py": GenConanfile("cmake", "3.31.6").with_shared_option(True),
            "app/conanfile.py": conanfile})

    c.run("create cmake")
    c.run("install app")
    # It doesn't hang, and it sees correctly just 1 dependency
    assert "NUM DEPS: 1" in c.out
