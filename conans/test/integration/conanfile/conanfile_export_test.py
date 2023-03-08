import os
import textwrap
from conans.test.utils.tools import TestClient


def test_inherited_baseclass():

    c = TestClient()

    conanfile_base = textwrap.dedent("""
        from conan import ConanFile
        import os

        class Base(ConanFile):
            version = "0.1"

            def export(self):
                self.copy('*', src=os.path.dirname(__file__), dst=self.export_folder)
                assert os.path.isfile( os.path.join(self.export_folder, os.path.basename(__file__)) )

            def build(self):
                self.output.info(f"build of {self.name}")

            def package_info(self):
                self.output.info(f"package_info of {self.name}")
                self.output.info(f"using conanfile_base {__file__}")
    """)

    conanfile_pkg = textwrap.dedent("""
        import conanfile_base

        class Pkg(conanfile_base.Base):
            name = "{name}"
            exports = "conanfile_base.py"

    """)

    conanfile_app = textwrap.dedent("""
        import conanfile_base

        class Pkg(conanfile_base.Base):
            name = "app"
            exports = "conanfile_base.py"

            def requirements(self):
                self.requires("pkg1/0.1")
                self.requires("pkg2/0.1")
                self.output.info(f"using conanfile_base {conanfile_base.__file__}")
    """)

    c.save({"pkg1/conanfile.py": conanfile_pkg.format(name="pkg1"),
            "pkg2/conanfile.py": conanfile_pkg.format(name="pkg2"),
            "base/conanfile_base.py": conanfile_base,
            "app/conanfile.py": conanfile_app})

    base_path = os.path.join(c.current_folder, "base")
    app_path = os.path.join(c.current_folder, "app")

    # copy the base python file to all projects that use that
    # you can do this easily with a scripts that reads the
    # conanfile and detect the recipes that are importing the
    # base module
    c.run_command("cp base/conanfile_base.py pkg1")
    c.run_command("cp base/conanfile_base.py pkg2")
    c.run_command("cp base/conanfile_base.py app")

    c.run("export pkg1")
    c.run("export pkg2")
    c.run("install app --build=missing")
    print(c.out)

    assert f"pkg1/0.1: build of pkg1" in c.out
    assert f"pkg1/0.1: package_info of pkg1" in c.out
    assert f"pkg1/0.1: using conanfile_base {c.cache_folder}/data/pkg1/0.1/_/_/export/conanfile_base.py" in c.out

    assert f"pkg2/0.1: package_info of pkg2" in c.out
    assert f"pkg2/0.1: build of pkg2" in c.out
    assert f"pkg2/0.1: using conanfile_base {c.cache_folder}/data/pkg2/0.1/_/_/export/conanfile_base.py" in c.out

    assert f"conanfile.py (app/0.1): using conanfile_base {app_path}/conanfile_base.py" in c.out

    # you could clean after this
    c.run_command("rm pkg1/conanfile_base.py")
    c.run_command("rm pkg2/conanfile_base.py")
    c.run_command("rm app/conanfile_base.py")
