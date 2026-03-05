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


class TestPackageIDABIOptions:
    """
    These tests use the ``shared=True/False`` options for a proxy of the real issue
    reported in https://github.com/conan-io/conan/issues/19108

    The issue appears in MSVC when headers define

    define FOO_EXPORT __declspec(dllimport)

    Then, a static library will be a different artifact if it links against a static library
    or a shared library. This isn't a very common issue because of 2 reasons:
    - The most general linkage method are either all static or all shared, it is not that frequent
      to have static libraries linking shared libraries
    - Many third parties and open source libraries declare and use the __declspec(dllexport),
      which is necessary for correctly exporting the symbols in MSVC. But the dllimport is not
      that necessary and mostly a linking optimization, so not that frequent
    """
    def test_package_id_abi_options(self):
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                package_id_abi_options = ["shared"]
            """)
        app = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "0.1"
                package_type = "static-library"
                requires = "pkg/0.1"
            """)
        c.save({"pkg/conanfile.py": conanfile,
                "app/conanfile.py": app})
        c.run("create pkg")
        c.run("create pkg -o *:shared=True")

        c.run("create app")
        c.assert_listed_binary({"app": ("e822341e143eb3bba372e24b7cd908c8f91dc24e", "Build")})
        c.run("list app/0.1:e822341e143eb3bba372e24b7cd908c8f91dc24e")
        assert "pkg/*:shared: False" in c.out

        c.run("create app -o *:shared=True")
        c.assert_listed_binary({"app": ("8c15f2b19bd994dcd5b44780eda3f03bde74c217", "Build")})
        c.run("list app/0.1:8c15f2b19bd994dcd5b44780eda3f03bde74c217")
        assert "pkg/*:shared: True" in c.out

    def test_package_id_abi_options_conditional(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                settings = "os"

                def configure(self):
                    if self.settings.os == "Windows":
                        self.package_id_abi_options = ["shared"]
            """)
        app = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "0.1"
                package_type = "static-library"
                requires = "pkg/0.1"
            """)
        c.save({"pkg/conanfile.py": conanfile,
                "app/conanfile.py": app})
        c.run("create pkg -s os=Linux")
        c.run("create pkg -s os=Linux -o *:shared=True")
        c.run("create pkg -s os=Windows")
        c.run("create pkg -s os=Windows -o *:shared=True")

        c.run("create app -s os=Linux")
        c.assert_listed_binary({"app": ("e250b55435052b5e55b151d0b03900c73d262473", "Build")})
        c.run("list app/0.1:e250b55435052b5e55b151d0b03900c73d262473")
        assert "pkg/*:shared: False" not in c.out

        c.run("create app -o *:shared=True -s os=Linux --build=missing:&")
        c.assert_listed_binary({"app": ("e250b55435052b5e55b151d0b03900c73d262473", "Cache")})

        c.run("create app -s os=Windows")
        c.assert_listed_binary({"app": ("e822341e143eb3bba372e24b7cd908c8f91dc24e", "Build")})
        c.run("list app/0.1:e822341e143eb3bba372e24b7cd908c8f91dc24e")
        assert "pkg/*:shared: False" in c.out

        c.run("create app -o *:shared=True -s os=Windows --build=missing:&")
        c.assert_listed_binary({"app": ("8c15f2b19bd994dcd5b44780eda3f03bde74c217", "Build")})
        c.run("list app/0.1:8c15f2b19bd994dcd5b44780eda3f03bde74c217")
        assert "pkg/*:shared: True" in c.out

    def test_package_id_abi_options_transitive(self):
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                package_id_abi_options = ["shared"]
            """)
        middle = (GenConanfile("middle", "0.1").with_requires("pkg/0.1")
                                               .with_package_type("shared-library"))
        app = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "0.1"
                package_type = "application"
                requires = "middle/0.1"
            """)
        c.save({"pkg/conanfile.py": conanfile,
                "middle/conanfile.py": middle,
                "app/conanfile.py": app})
        c.run("create pkg")
        c.run("create pkg -o *:shared=True")
        c.run("create middle")
        c.run("create middle -o *:shared=True")

        c.run("create app")
        c.assert_listed_binary({"app": ("6da48adc0fa03ddc8b74de14b3fd5513a3688a52", "Build")})
        # binary not affected, because headers not propagated!
        c.run("list app/0.1:6da48adc0fa03ddc8b74de14b3fd5513a3688a52")
        assert "pkg/*:shared: False" not in c.out

        c.run("create app -o *:shared=True")
        # Still affected by "middle" full package-id, that is static
        c.assert_listed_binary({"app": ("6da48adc0fa03ddc8b74de14b3fd5513a3688a52", "Build")})
        c.run("list app/0.1:6da48adc0fa03ddc8b74de14b3fd5513a3688a52")
        assert "pkg/*:shared: False" not in c.out

        # But if the header is propagated
        middle = (GenConanfile("middle", "0.1").with_requirement("pkg/0.1", transitive_headers=True)
                  .with_package_type("shared-library"))
        c.save({"middle/conanfile.py": middle})
        c.run("create middle")
        c.run("create middle -o *:shared=True")

        c.run("create app")
        c.assert_listed_binary({"app": ("ae20c28d303d1c561f95683add6638d6155c2bd9", "Build")})
        c.run("list app/0.1:ae20c28d303d1c561f95683add6638d6155c2bd9")
        assert "pkg/*:shared: False" in c.out

        c.run("create app -o *:shared=True")
        # Still affected by "middle" full package-id, that is static
        c.assert_listed_binary({"app": ("321ad086fc1bbb3c2cf7f3e4d8d69c6d2096196d", "Build")})
        c.run("list app/0.1:321ad086fc1bbb3c2cf7f3e4d8d69c6d2096196d")
        assert "pkg/*:shared: True" in c.out
