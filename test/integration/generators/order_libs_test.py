import platform

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_library_order():
    #
    # project -> sdl2_ttf -> freetype ------------> bzip2
    #             \             \----->libpng  -> zlib
    #              \------> sdl2----------------->/
    # Order: sdl2_ttf freetype sdl2 libpng zlib bzip

    c = TestClient()

    def _export(libname, refs=None):
        conanfile = GenConanfile(libname, "0.1").with_package_info(cpp_info={"libs": [libname]},
                                                                   env_info={})
        for r in refs or []:
            conanfile.with_requires(f"{r}/0.1")
        c.save({"conanfile.py": conanfile}, clean_first=True)
        c.run("export .")

    _export("zlib")
    _export("bzip2")
    _export("sdl2", ["zlib"])
    _export("libpng", ["zlib"])
    _export("freetype", ["bzip2", "libpng"])
    _export("sdl2_ttf", ["freetype", "sdl2"])
    _export("app", ["sdl2_ttf"])

    c.run("install . --build missing -g AutotoolsDeps")

    deps = "conanautotoolsdeps.bat" if platform.system() == "Windows" else "conanautotoolsdeps.sh"
    autotoolsdeps = c.load(deps)
    assert '-lsdl2_ttf -lfreetype -lsdl2 -llibpng -lzlib -lbzip2' in autotoolsdeps


# TODO: Add a test that manages too system libs
