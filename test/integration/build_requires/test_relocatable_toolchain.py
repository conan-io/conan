import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_relocatable_toolchain():
    """ Implements the following use case:
    - base/1.0 implements an SDK that needs to be relocated in every maching, but this package
      contains the non relocatable part and the relocation scripts
    - sdk/1.0 --tool_requires-> base/1.0 and implements just the relocation execution, copying
      whatever is necessary from base, and relocating it.
      It defines build_policy = "missing" and upload policy = "skip"
    https://github.com/conan-io/conan/issues/5059
    """
    c = TestClient(default_server_user=True)
    base = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save, copy
        class Pkg(ConanFile):
            name = "base"
            version = "1.0"
            settings = "arch"

            def build(self):
                save(self, "sdk.txt", f"arch:{self.settings.arch}=>{self.settings_target.arch}")

            def package(self):
                copy(self, "*", self.build_folder, self.package_folder)
        """)
    sdk = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load, copy, save
        class Pkg(ConanFile):
            name = "sdk"
            version = "1.0"
            settings = "arch"
            build_policy = "missing"
            upload_policy = "skip"

            def build_requirements(self):
                self.tool_requires("base/1.0")

            def package(self):
                # Whatever modification, customization, RPATHs, symlinks, etc
                pkg_folder = self.dependencies.build["base"].package_folder
                sdk = load(self, os.path.join(pkg_folder, "sdk.txt"))
                save(self, os.path.join(self.package_folder, "sdk.txt"), "CUSTOM PATH: " + sdk)

            def package_info(self):
                self.output.info(f"SDK INFO: {load(self, 'sdk.txt')}!!!")
        """)
    c.save({"linux": "[settings]\nos=Linux\narch=x86_64",
            "embedded": "[settings]\narch=armv8",
            "base/conanfile.py": base,
            "sdk/conanfile.py": sdk,
            "consumer/conanfile.py": GenConanfile("app", "1.0").with_tool_requires("sdk/1.0")})
    c.run("create base -pr:h=embedded -pr:b=linux --build-require")
    c.run("export sdk")
    c.run("install consumer -pr:h=embedded -pr:b=linux")
    c.assert_listed_binary({"base/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Cache"),
                            "sdk/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Build")},
                           build=True)
    assert "sdk/1.0: Calling package()" in c.out
    assert "sdk/1.0: SDK INFO: CUSTOM PATH: arch:x86_64=>armv8!!!" in c.out

    c.run("install consumer -pr:h=embedded -pr:b=linux -v")
    c.assert_listed_binary({"base/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Skip"),
                            "sdk/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Cache")},
                           build=True)
    assert "sdk/1.0: Calling package()" not in c.out
    assert "sdk/1.0: SDK INFO: CUSTOM PATH: arch:x86_64=>armv8!!!" in c.out

    # If I upload everything and remove:
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("install consumer -pr:h=embedded -pr:b=linux")
    c.assert_listed_binary(
        {"base/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Download (default)"),
         "sdk/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Build")},
        build=True)
    assert "sdk/1.0: Calling package()" in c.out
    assert "sdk/1.0: SDK INFO: CUSTOM PATH: arch:x86_64=>armv8!!!" in c.out

    # we can even remove the binary!
    c.run("remove base/1.0:* -c")
    c.run("install consumer -pr:h=embedded -pr:b=linux -v")
    c.assert_listed_binary({"base/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Skip"),
                            "sdk/1.0": ("62e589af96a19807968167026d906e63ed4de1f5", "Cache")},
                           build=True)
    assert "sdk/1.0: SDK INFO: CUSTOM PATH: arch:x86_64=>armv8!!!" in c.out
