import os

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cache_in_layout():
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires.
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . base/1.0@")

    conan_file = str(GenConanfile().with_import("from conans import tools").with_import("import os").
                     with_require("base/1.0").
                     with_generator("cmake_find_package"))

    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    conan_file += """
    no_copy_sources = True

    def configure(self):
        self.layout.source.folder = "my_sources"
        self.layout.build.folder = "my_build"
        self.layout.package.folder = "my_package"

    def source(self):
        self.output.warn("Source folder: {}".format(self.source_folder))
        tools.save("source.h", "foo")

    def build(self):
        self.output.warn("Build folder: {}".format(self.build_folder))
        tools.save("build.lib", "bar")

    def package(self):
        self.output.warn("Package folder: {}".format(self.package_folder))
        tools.save(os.path.join(self.package_folder, "LICENSE"), "bar")

    """
    client.save({"conanfile.py": conan_file})
    client.run("create . lib/1.0@")
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "58083437fe22ef1faaa0ab4bb21d0a95bf28ae3d")
    sf = client.cache.package_layout(ref).source()
    bf = client.cache.package_layout(ref).build(pref)
    pf = client.cache.package_layout(ref).package(pref)

    csf = os.path.join(sf, "my_sources")
    cbf = os.path.join(bf, "my_build")
    cpf = os.path.join(pf, "my_package")
    # Check folders match with the declared by the layout
    assert "Source folder: {}".format(csf) in client.out
    assert "Build folder: {}".format(cbf) in client.out
    assert "Package folder: {}".format(cpf) in client.out

    # Check the source folder
    assert os.path.exists(os.path.join(csf, "source.h"))

    # Check the build folder
    assert os.path.exists(os.path.join(cbf, "build.lib"))

    # Check the package folder
    assert os.path.exists(os.path.join(cpf, "LICENSE"))
