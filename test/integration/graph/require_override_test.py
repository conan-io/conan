from conan.test.utils.tools import TestClient, GenConanfile


class TestRequireOverride:

    def test_override_user_channel(self):
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": GenConanfile(),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep1/0.1")
                                                              .with_requires("dep2/0.1@us/chan"),
                "app/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                  .with_requirement("dep1/0.1@us/chan",
                                                                    override=True)
                                                  .with_requirement("dep2/0.1", override=True)})
        c.run("create dep --name=dep1 --version=0.1")
        c.run("create dep --name=dep1 --version=0.1 --user=us --channel=chan")
        c.run("create dep --name=dep2 --version=0.1")
        c.run("create dep --name=dep2 --version=0.1 --user=us --channel=chan")
        c.run("export pkg")
        c.run("graph info app")
        c.assert_overrides({"dep1/0.1": ['dep1/0.1@us/chan'],
                            "dep2/0.1@us/chan": ['dep2/0.1']})
        c.assert_listed_require({"dep1/0.1@us/chan": "Cache",
                                 "dep2/0.1": "Cache"})

    def test_can_override_even_versions_with_build_metadata(self):
        # https://github.com/conan-io/conan/issues/5900
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("lib")})
        c.run("create . --version=1.0+abc")
        c.run("create . --version=1.0+xyz")

        c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_require("lib/1.0+abc")})
        c.run("create .")

        c.save({"conanfile.py": GenConanfile().with_require("pkg/1.0")
                                              .with_requirement("lib/1.0+xyz", override=True)})
        c.run("graph info .")
        c.assert_overrides({"lib/1.0+abc": ['lib/1.0+xyz']})
        c.assert_listed_require({"lib/1.0+xyz": "Cache",
                                 "pkg/1.0": "Cache"})

