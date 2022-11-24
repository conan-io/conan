import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_editable_envvars():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            def layout(self):
                self.folders.source = "mysource"
                self.folders.build = "mybuild"
                self.cpp.source.runenv_info.append_path("MYRUNPATH", "mylocalsrc")
                self.cpp.build.buildenv_info.define_path("MYBUILDPATH", "mylocalbuild")
        """)

    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile().with_settings("os")
                                              .with_requires("dep/1.0")
                                              .with_generator("VirtualBuildEnv")
                                              .with_generator("VirtualRunEnv")})
    c.run("editable add dep dep/1.0")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    build_path = os.path.join(c.current_folder, "dep", "mybuild", "mylocalbuild")
    buildenv = c.load("conanbuildenv.sh")
    assert f'export MYBUILDPATH="{build_path}"' in buildenv
    runenv = c.load("conanrunenv.sh")
    run_path = os.path.join(c.current_folder, "dep", "mysource", "mylocalsrc")
    assert f'export MYRUNPATH="$MYRUNPATH:{run_path}"' in runenv


def test_editable_conf():
    c = TestClient()
    # TODO: Define if we want conf.xxxx_path(), instead of (..., path=True) methods
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            def layout(self):
                self.folders.source = "mysource"
                self.folders.build = "mybuild"
                self.cpp.source.conf_info.append("myconf", "mylocalsrc", path=True)
                self.cpp.build.conf_info.append("myconf", "mylocalbuild", path=True)
        """)

    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/1.0"
            def generate(self):
                conf = self.dependencies["dep"].conf_info.get("myconf")
                self.output.info(f"CONF: {conf}")
        """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg})
    c.run("editable add dep dep/1.0")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    out = str(c.out).replace("\\\\", "\\")
    build_path = os.path.join(c.current_folder, "dep", "mybuild", "mylocalbuild")
    run_path = os.path.join(c.current_folder, "dep", "mysource", "mylocalsrc")
    assert build_path in out
    assert run_path in out
