import os
import re
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_editable_envvars():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
            def layout(self):
                self.folders.source = "mysource"
                self.folders.build = "mybuild"
                self.layouts.source.runenv_info.append_path("MYRUNPATH", "mylocalsrc")
                self.layouts.build.buildenv_info.define_path("MYBUILDPATH", "mylocalbuild")

                self.layouts.package.buildenv_info.define_path("MYBUILDPATH", "mypkgbuild")
                self.layouts.package.runenv_info.append_path("MYRUNTPATH", "mypkgsrc")

            def package_info(self):
                self.buildenv_info.define("OTHERVAR", "randomvalue")
        """)

    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile().with_settings("os")
                                              .with_requires("dep/1.0")
                                              .with_generator("VirtualBuildEnv")
                                              .with_generator("VirtualRunEnv")})
    c.run("editable add dep  --name=dep --version=1.0")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    build_path = os.path.join(c.current_folder, "dep", "mybuild", "mylocalbuild")
    buildenv = c.load("pkg/conanbuildenv.sh")
    assert f'export MYBUILDPATH="{build_path}"' in buildenv

    runenv = c.load("pkg/conanrunenv.sh")
    # The package_info() buildenv is aggregated, no prob
    # But don't use same vars
    assert 'export OTHERVAR="randomvalue"' in buildenv
    run_path = os.path.join(c.current_folder, "dep", "mysource", "mylocalsrc")
    assert f'export MYRUNPATH="$MYRUNPATH:{run_path}"' in runenv

    c.run("editable remove dep")
    c.run("create dep")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    buildenv = c.load("pkg/conanbuildenv.sh")
    assert 'mypkgbuild' in buildenv
    assert "mylocalbuild" not in buildenv
    assert 'export OTHERVAR="randomvalue"' in buildenv
    runenv = c.load("pkg/conanrunenv.sh")
    assert 'mypkgsrc' in runenv
    assert "mylocalsrc" not in runenv


def test_editable_conf():
    c = TestClient()
    # TODO: Define if we want conf.xxxx_path(), instead of (..., path=True) methods
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            def layout(self):
                self.folders.source = "mysource"
                self.folders.build = "mybuild"
                self.layouts.source.conf_info.append_path("user:myconf", "mylocalsrc")
                self.layouts.build.conf_info.append_path("user:myconf", "mylocalbuild")
                self.layouts.build.conf_info.update_path("user:mydictconf", {"a": "mypatha", "b": "mypathb"})
                self.layouts.build.conf_info.define_path("user:mydictconf2", {"c": "mypathc"})
        """)

    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/1.0"
            def generate(self):
                conf = self.dependencies["dep"].conf_info.get("user:myconf")
                self.output.info(f"CONF: {conf}")
                dictconf = self.dependencies["dep"].conf_info.get("user:mydictconf", check_type=dict)
                self.output.info(f"CONFDICT: {dictconf}")
                dictconf2 = self.dependencies["dep"].conf_info.get("user:mydictconf2", check_type=dict)
                self.output.info(f"CONFDICT: {dictconf2}")
        """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg})
    c.run("editable add dep --name=dep --version=1.0")
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


def test_editable_conf_tool_require_builtin():
    c = TestClient()
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Dep(ConanFile):
            name = "androidndk"
            version = "1.0"
            def layout(self):
                self.layouts.build.conf_info.define_path("tools.android:ndk_path", "mybuild")
                self.layouts.package.conf_info.define_path("tools.android:ndk_path", "mypkg")
        """)

    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            tool_requires = "androidndk/1.0"
            def generate(self):
                ndk = self.conf.get("tools.android:ndk_path")
                self.output.info(f"NDK: {ndk}!!!")
        """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg})
    c.run("editable add dep")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    ndk_path = os.path.join(c.current_folder, "dep", "mybuild")
    assert f"conanfile.py: NDK: {ndk_path}!!!" in c.out

    c.run("editable remove dep")
    c.run("create dep")
    c.run("install pkg -s os=Linux -s:b os=Linux")
    assert re.search("conanfile.py: NDK: .*mypkg!!!", str(c.out))
