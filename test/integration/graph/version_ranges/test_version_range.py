from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_version_range_with_revisions():
    tc = TestClient()
    tc.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    tc.run("export .")
    rrev1 = tc.exported_recipe_revision()
    tc.save({"conanfile.py": GenConanfile("pkg", "1.0").with_class_attribute("# a comment")})
    tc.run("export .")
    rrev2 = tc.exported_recipe_revision()
    assert rrev1 != rrev2

    tc.run(f"install --requires=pkg/[>=1.0]#{rrev1} --build=missing -vv")
    assert f"WARN: risk: Specifying a revision for requirement 'pkg/[>=1.0]#{rrev1}' together with a version range has no effect" in tc.out
    # Note, rrev2 instead of the requested rrev1
    assert f"pkg/1.0#{rrev2} - Cache" in tc.out
