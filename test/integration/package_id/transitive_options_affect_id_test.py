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
        c = TestClient()
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

    def test_package_id_abi_options_important(self):
        # The "!" important marker only defines the precedence of the option value, it must
        # not be part of the consumer package_id
        c = TestClient()
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
        c.run("create pkg -o *:shared=True")

        c.run("create app -o *:shared=True")
        c.assert_listed_binary({"app": ("8c15f2b19bd994dcd5b44780eda3f03bde74c217", "Build")})
        c.run("list app/0.1:8c15f2b19bd994dcd5b44780eda3f03bde74c217")
        assert "pkg/*:shared: True" in c.out

        c.run("create app -o pkg/*:shared!=True")
        c.assert_listed_binary({"app": ("8c15f2b19bd994dcd5b44780eda3f03bde74c217", "Build")})
        c.run("list app/0.1:*")
        assert "shared!" not in c.out

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
        c = TestClient()
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

    def test_package_id_abi_options_not_compatible(self):
        # https://github.com/conan-io/conan/issues/20535
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            class Dep(ConanFile):
                name = "dep"
                version = "1.0"
                package_type = "static-library"
                settings = "os", "arch", "compiler", "build_type"
                options = {"my_option": [True, False]}
                default_options = {"my_option": True}
            """)
        pkg = (GenConanfile("pkg", "1.0").with_package_type("static-library")
                                         .with_settings("os", "arch", "compiler", "build_type")
                                         .with_requires("dep/1.0"))
        c.save({"dep/conanfile.py": dep,
                "pkg/conanfile.py": pkg})
        # Pin a profile that has compatible configurations (cppstd) in the default plugin
        settings = ("-s os=Linux -s arch=x86_64 -s build_type=Release -s compiler=gcc "
                    "-s compiler.version=11 -s compiler.libcxx=libstdc++11 -s compiler.cppstd=17")
        c.run(f"create dep {settings} -o dep/*:my_option=True")
        assert "Exported: dep/1.0#4efc12119b7f473f935add98befdb4ee" in c.out
        c.run(f"create pkg {settings} -o dep/*:my_option=True")

        # dep now declares that "my_option" affects consumers' ABI
        dep += '    package_id_abi_options = ["my_option"]\n'
        c.save({"dep/conanfile.py": dep})
        c.run(f"create dep {settings} -o dep/*:my_option=False")
        assert "Exported: dep/1.0#f7918c0a0d520d7371abdd654efb5a06" in c.out
        c.run(f"install --requires=pkg/1.0 {settings} -o dep/*:my_option=False", assert_error=True)
        # The binary built against my_option=True must not be picked as "compatible"
        assert "Found compatible package" not in c.out
        assert "ERROR: Missing binary: pkg/1.0" in c.out

    def test_package_id_abi_options_build_id(self):
        # build_id() clones the info, that contains the dependency package_id_abi_options
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            class Dep(ConanFile):
                name = "dep"
                version = "0.1"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                package_id_abi_options = ["shared"]
            """)
        pkg = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                package_type = "static-library"
                settings = "build_type"
                requires = "dep/0.1"

                def build_id(self):
                    self.info_build.settings.build_type = "Any"

                def build(self):
                    self.output.info("Building my code!")

                def package(self):
                    self.output.info(f"Packaging {self.settings.build_type}!")
            """)
        c.save({"dep/conanfile.py": dep,
                "pkg/conanfile.py": pkg})
        c.run("create dep")
        c.run("create dep -o *:shared=True")

        # Release builds, Debug reuses the build of Release, as build_type is not part of build_id
        c.run("create pkg -s build_type=Release")
        c.assert_listed_binary({"pkg": ("1decfe03fedc46d5c3d695988d84922400dc3f06", "Build")})
        assert "Building my code!" in c.out
        assert "Packaging Release!" in c.out
        c.run("create pkg -s build_type=Debug")
        assert "Building my code!" not in c.out
        assert "Packaging Debug!" in c.out

        # The dependency "shared" option is part of the build_id too, it must build again
        c.run("create pkg -s build_type=Release -o *:shared=True")
        c.assert_listed_binary({"pkg": ("ed472c627b10eb524ec5cd08f250776a988c7b31", "Build")})
        assert "Building my code!" in c.out
        assert "Packaging Release!" in c.out
        c.run("create pkg -s build_type=Debug -o *:shared=True")
        assert "Building my code!" not in c.out
        assert "Packaging Debug!" in c.out

        c.run("list pkg/0.1:*")
        assert c.out.count("dep/*:shared: False") == 2
        assert c.out.count("dep/*:shared: True") == 2
