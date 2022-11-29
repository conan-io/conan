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
    print(c.out)
    build_path = os.path.join(c.current_folder, "dep", "mybuild", "mylocalbuild")
    buildenv = c.load("pkg/conanbuildenv.sh")
    assert f'export MYBUILDPATH="{build_path}"' in buildenv
    runenv = c.load("pkg/conanrunenv.sh")
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
                self.cpp.source.conf_info.append_path("user.myconf", "mylocalsrc")
                self.cpp.build.conf_info.append_path("user.myconf", "mylocalbuild")
                self.cpp.build.conf_info.update_path("user.mydictconf", {"a": "mypatha", "b": "mypathb"})
                self.cpp.build.conf_info.define_path("user.mydictconf2", {"c": "mypathc"})
        """)

    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/1.0"
            def generate(self):
                conf = self.dependencies["dep"].conf_info.get("user.myconf")
                self.output.info(f"CONF: {conf}")
                dictconf = self.dependencies["dep"].conf_info.get("user.mydictconf", check_type=dict)
                self.output.info(f"CONFDICT: {dictconf}")
                dictconf2 = self.dependencies["dep"].conf_info.get("user.mydictconf2", check_type=dict)
                self.output.info(f"CONFDICT: {dictconf2}")
        """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg})
    c.run("editable add dep dep/1.0")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    out = str(c.out).replace("\\\\", "\\")
    conf_source = os.path.join(c.current_folder, "dep", "mybuild", "mylocalbuild")
    conf_build = os.path.join(c.current_folder, "dep", "mysource", "mylocalsrc")
    confdict1 = os.path.join(c.current_folder, "dep", "mybuild", "mypatha")
    confdict2 = os.path.join(c.current_folder, "dep", "mybuild", "mypathc")
    assert conf_source in out
    assert conf_build in out
    assert confdict1 in out
    assert confdict2 in out
