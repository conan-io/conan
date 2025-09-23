import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestTransitiveOptionsAffectPackageID:

    def test_basic(self):
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_option("noaffect", [1, 2])\
                                              .with_option("affect", [True, False])\
                                              .with_package_type("static-library")
        client.save({"conanfile.py": conanfile})
        client.run("create . -o pkg*:noaffect=1 -o pkg*:affect=False")
        client.assert_listed_binary({"pkg": ("7ff068ae587920b4f40b0dd81e891808c419f78c", "Build")})

        client.run("create . -o pkg*:noaffect=2 -o pkg*:affect=False")
        client.assert_listed_binary({"pkg": ("66de80286b3d7ae1d5c05a9b795d6a6e622a778e", "Build")})

        client.run("create . -o pkg*:noaffect=1 -o pkg*:affect=True")
        client.assert_listed_binary({"pkg": ("8e0cdf1d5b1c1c557b6f4b4ec01a4383b8f50dc3", "Build")})

        client.run("create . -o pkg*:noaffect=2 -o pkg*:affect=True")
        client.assert_listed_binary({"pkg": ("4a18825b7c66155f03b27a1963e42ab3a836fd28", "Build")})

        app = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "0.1"
                package_type = "application"
                requires = "pkg/0.1"
                def package_id(self):
                    if self.dependencies["pkg"].package_type == "static-library":
                        self.output.info("EMBED MODE!!")
                        self.info.requires["pkg"].package_id = None
                        self.info.options["pkg/*"].affect = self.dependencies["pkg"].options.affect
            """)
        client.save({"conanfile.py": app})
        client.run("create . -o pkg*:noaffect=1 -o pkg*:affect=False")
        assert "EMBED MODE!!" in client.out
        common_pkg_id = "2060adfe3cc9040e5ee7e54c783d752f9ca1ba43"  # Should be the same!
        client.assert_listed_binary({"app": (common_pkg_id, "Build")})
        client.run("create . -o pkg*:noaffect=2 -o pkg*:affect=False")
        assert "EMBED MODE!!" in client.out
        client.assert_listed_binary({"app": (common_pkg_id, "Build")})

        client.run("create . -o pkg*:noaffect=1 -o pkg*:affect=True")
        assert "EMBED MODE!!" in client.out
        different_pkg_id = "acfad205713f0d2fce61e7927d059635c0abbfff"  # Should be the same!
        client.assert_listed_binary({"app": (different_pkg_id, "Build")})
        client.run("create . -o pkg*:noaffect=2 -o pkg*:affect=True")
        assert "EMBED MODE!!" in client.out
        client.assert_listed_binary({"app": (different_pkg_id, "Build")})

    def test_transitive_shared(self):
        # https://github.com/conan-io/conan/issues/18900
        c = TestClient()

        lib1 = GenConanfile("lib1", "0.1").with_shared_option(True)
        lib2 = (GenConanfile("lib2", "0.1").with_shared_option(True)
                .with_requirement("lib1/0.1", transitive_libs=True))
        lib3 = (GenConanfile("lib3", "0.1").with_shared_option(True)
                .with_requirement("lib2/0.1"))
        lib4 = (GenConanfile("lib4", "0.1").with_shared_option(True)
                .with_requirement("lib3/0.1"))
        c.save({"lib1/conanfile.py": lib1,
                "lib2/conanfile.py": lib2,
                "lib3/conanfile.py": lib3,
                "lib4/conanfile.py": lib4})
        c.run("create lib1")
        c.run("create lib2")
        c.run("create lib3")
        c.run("create lib4")

        c.run("install --requires=lib4/0.1 -o lib1/*:shared=False --build=missing")
        c.assert_listed_binary({"lib1/0.1": ("55c609fe8808aa5308134cb5989d23d3caffccf2", "Build"),
                                "lib2/0.1": ("76844632e497abea8503d65ffd8324460dc70745", "Build"),
                                "lib3/0.1": ("7b10301e532fc0269d6ac70470aee5780f0836cd", "Build"),
                                "lib4/0.1": ("635372f179ad582c713637e361a7cd7ac7cd1d09", "Cache"),
                                })

        lib3 = (GenConanfile("lib3", "0.1").with_shared_option(True)
                .with_requirement("lib2/0.1", transitive_libs=True))
        c.save({"lib3/conanfile.py": lib3})
        c.run("remove * -c")
        c.run("create lib1")
        c.run("create lib2")
        c.run("create lib3")
        c.run("create lib4")
        c.run("install --requires=lib4/0.1 -o lib1/*:shared=False --build=missing")
        c.assert_listed_binary({"lib1/0.1": ("55c609fe8808aa5308134cb5989d23d3caffccf2", "Build"),
                                "lib2/0.1": ("76844632e497abea8503d65ffd8324460dc70745", "Build"),
                                "lib3/0.1": ("7b10301e532fc0269d6ac70470aee5780f0836cd", "Build"),
                                "lib4/0.1": ("dd8f5355b399fd7d96c883ddd39b992ae968cb14", "Build"),
                                })
