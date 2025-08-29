import json
import os
import shutil
import textwrap

import pytest

from conan.api.subapi.workspace import WorkspaceAPI
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save_files
from conan.tools.files import replace_in_file

WorkspaceAPI.TEST_ENABLED = "will_break_next"


class TestWorkspaceRoot:

    def test_workspace_root(self):
        c = TestClient(light=True)
        # Just check the root command works
        c.run("workspace root", assert_error=True)
        assert "ERROR: Workspace not defined, please create" in c.out

        # error, conanws/ folder does not contain conanws.[py | yml]
        c.save({"conanws/test.txt": ""})
        with c.chdir("conanws"):
            c.run("workspace root", assert_error=True)
            assert "ERROR: Workspace not defined, please create" in c.out
            c.save({"conanws.yml": ""})
            c.run("workspace root")
            assert c.current_folder in c.stdout

        # error, empty .py
        c.save({"conanws.py": ""}, clean_first=True)
        c.run("workspace root", assert_error=True)
        assert "Error loading conanws.py" in c.out
        assert "No subclass of Workspace" in c.out

        c.save({"conanws.yml": ""}, clean_first=True)
        c.run("workspace root")
        assert c.current_folder in c.stdout


class TestAddRemove:

    def test_add(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "dep2/conanfile.py": GenConanfile("dep2", "0.1"),
                "dep3/conanfile.py": GenConanfile("dep3", "0.1")})
        c.run("workspace add dep1")
        assert "Reference 'dep1/0.1' added to workspace" in c.out
        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out
        c.run("editable list")  # No editables in global
        assert "dep1" not in c.out
        assert "dep2" not in c.out
        c.run("workspace add dep2")
        assert "Reference 'dep2/0.1' added to workspace" in c.out
        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        with c.chdir(temp_folder()):  # If we move to another folder, outside WS, no editables
            c.run("editable list")
            assert "dep1" not in c.out
            assert "dep2" not in c.out

        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace remove dep1")
        c.run("workspace info")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace remove dep2")
        c.run("workspace info")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" not in c.out

    def test_add_from_outside(self):
        c = TestClient(light=True)
        c.save({"sub/conanws.yml": "",
                "sub/dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "sub/dep2/conanfile.py": GenConanfile("dep2", "0.1")})
        with c.chdir("sub"):
            c.run("workspace add dep1")
            assert "Reference 'dep1/0.1' added to workspace" in c.out
            c.run("workspace add dep2")
            assert "Reference 'dep2/0.1' added to workspace" in c.out
            c.run("workspace info")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" in c.out
        assert c.load_home("editable_packages.json") is None

        c.run("editable list")
        assert "dep1" not in c.out
        assert "dep2" not in c.out
        assert c.load_home("editable_packages.json") is None
        with c.chdir("sub"):
            c.run("editable add dep1")
            assert c.load_home("editable_packages.json") is not None
            c.run("editable list")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" not in c.out
            c.run("workspace info")
            assert "dep1" in c.out
            assert "dep2" in c.out

        c.run("editable list")
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out

    @pytest.mark.parametrize("api", [False, True])
    def test_dynamic_editables(self, api):
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import load
            class Lib(ConanFile):
                def set_name(self):
                    self.name = load(self, os.path.join(self.recipe_folder, "name.txt"))
                def set_version(self):
                    self.version = load(self, os.path.join(self.recipe_folder, "version.txt"))
            """)
        if not api:
            workspace = textwrap.dedent("""\
                import os
                from conan import Workspace

                class MyWorkspace(Workspace):
                    def packages(self):
                        result = []
                        for f in os.listdir(self.folder):
                            if os.path.isdir(os.path.join(self.folder, f)):
                                full_path = os.path.join(self.folder, f, "name.txt")
                                name = open(full_path).read().strip()
                                version = open(os.path.join(self.folder, f,
                                                            "version.txt")).read().strip()
                                result.append({"path": f, "ref": f"{name}/{version}"})
                        return result
                """)
        else:
            workspace = textwrap.dedent("""\
                import os
                from conan import Workspace

                class MyWorkspace(Workspace):
                    def packages(self):
                        result = []
                        for f in os.listdir(self.folder):
                            if os.path.isdir(os.path.join(self.folder, f)):
                                conanfile = self.load_conanfile(f)
                                result.append({"path": f, "ref": f"{conanfile.name}/{conanfile.version}"})
                        return result
               """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile,
                "dep1/name.txt": "pkg",
                "dep1/version.txt": "2.1"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["packages"] == [{"ref": "pkg/2.1", "path": "dep1"}]
        c.save({"dep1/name.txt": "other",
                "dep1/version.txt": "14.5"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["packages"] == [{"ref": "other/14.5", "path": "dep1"}]
        c.run("install --requires=other/14.5")
        # Doesn't fail
        assert "other/14.5 - Editable" in c.out
        with c.chdir("dep1"):
            c.run("install --requires=other/14.5")
            # Doesn't fail
            assert "other/14.5 - Editable" in c.out

    def test_api_dynamic_version_run(self):
        # https://github.com/conan-io/conan/issues/17306
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from io import StringIO
            from conan import ConanFile
            class Lib(ConanFile):
                name= "pkg"
                def set_version(self):
                    my_buf = StringIO()
                    self.run('echo 2.1', stdout=my_buf)
                    self.version = my_buf.getvalue().strip()
            """)

        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def packages(self):
                    conanfile = self.load_conanfile("dep1")
                    return [{"path": "dep1", "ref": f"{conanfile.name}/{conanfile.version}"}]
            """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["packages"] == [{"ref": "pkg/2.1", "path": "dep1"}]
        c.run("install --requires=pkg/2.1")
        # it will not fail

    def test_error_uppercase(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "conanfile.py": GenConanfile("Pkg", "0.1")})
        c.run("workspace add .", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out
        c.save({"conanfile.py": GenConanfile()})
        c.run("workspace add . --name=Pkg --version=0.1", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out

    def test_add_open_error(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "dep/conanfile.py": GenConanfile("dep", "0.1")})
        c.run("workspace add dep")
        c.run("workspace open dep/0.1", assert_error=True)
        assert "ERROR: Can't open a dependency that is already an editable: dep/0.1" in c.out

    def test_remove_product(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "mydeppkg/conanfile.py": GenConanfile("mydeppkg", "0.1")})
        c.run("workspace add mydeppkg")
        c.run("workspace remove mydeppkg")
        c.run("workspace info")
        assert "mydeppkg" not in c.out

    def test_remove_removed_folder(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "mydeppkg/conanfile.py": GenConanfile("mydeppkg", "0.1")})
        c.run("workspace add mydeppkg")
        # If we now remove the folder
        shutil.rmtree(os.path.join(c.current_folder, "mydeppkg"))
        # It can still be removed by path, even if the path doesn't exist
        c.run("workspace remove mydeppkg")
        assert "Removed from workspace: mydeppkg" in c.out
        c.run("workspace info")
        assert "mydeppkg" not in c.out

    def test_custom_add_remove(self):
        c = TestClient(light=True)

        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def name(self):
                    return "myws"

                def add(self, ref, path, *args, **kwargs):
                    self.output.info(f"Adding {ref} at {path}")
                    super().add(ref, path, *args, **kwargs)

                def remove(self, path, *args, **kwargs):
                    self.output.info(f"Removing {path}")
                    return super().remove(path, *args, **kwargs)
            """)

        c.save({"conanws.py": workspace,
                "dep/conanfile.py": GenConanfile("dep", "0.1")})
        c.run("workspace add dep")
        assert "Workspace 'myws': Adding dep/0.1" in c.out
        c.run("workspace info")
        assert "dep/0.1" in c.out
        c.run("workspace remove dep")
        assert "Workspace 'myws': Removing" in c.out
        c.run("workspace info")
        assert "dep/0.1" not in c.out


class TestOpenAdd:
    def test_without_git(self):
        t = TestClient(default_server_user=True, light=True)
        t.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        t.run("create .")
        t.run("upload * -r=default -c")

        c = TestClient(servers=t.servers, light=True)
        c.run(f"workspace open pkg/0.1")
        assert "name = 'pkg'" in c.load("pkg/conanfile.py")

        # The add should work the same
        c2 = TestClient(servers=t.servers, light=True)
        c2.save({"conanws.yml": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert "name = 'pkg'" in c2.load("pkg/conanfile.py")
        c2.run("workspace info")
        assert "pkg/0.1" in c2.out

    def test_without_git_export_sources(self):
        t = TestClient(default_server_user=True, light=True)
        t.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports_sources("*.txt"),
                "CMakeLists.txt": "mycmake"})
        t.run("create .")
        t.run("upload * -r=default -c")

        c = TestClient(servers=t.servers)
        c.run("workspace open pkg/0.1")
        assert "name = 'pkg'" in c.load("pkg/conanfile.py")
        assert "mycmake" in c.load("pkg/CMakeLists.txt")

    def test_workspace_git_scm(self):
        folder = temp_folder()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def export(self):
                    git = Git(self)
                    git.coordinates_to_conandata()
            """)
        url, commit = create_local_git_repo(files={"conanfile.py": conanfile}, folder=folder,
                                            branch="mybranch")
        t1 = TestClient(default_server_user=True, light=True)
        t1.run_command('git clone "file://{}" .'.format(url))
        t1.run("create .")
        t1.run("upload * -r=default -c")

        c = TestClient(servers=t1.servers, light=True)
        c.run("workspace open pkg/0.1")
        assert c.load("pkg/conanfile.py") == conanfile

        c2 = TestClient(servers=t1.servers, light=True)
        c2.save({"conanws.yml": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert 'name = "pkg"' in c2.load("pkg/conanfile.py")
        c2.run("workspace info")
        assert "pkg/0.1" in c2.out

    def test_workspace_build_editables(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})

        c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_build_msg("BUILD PKGA!"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
                                                                .with_requires("pkga/0.1")})
        c.run("workspace add pkga")
        c.run("workspace add pkgb")

        c.run("install --requires=pkgb/0.1 --build=editable")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild"),
                                "pkgb/0.1": ("47a5f20ec8fb480e1c5794462089b01a3548fdc5",
                                             "EditableBuild")})
        assert "pkga/0.1: WARN: BUILD PKGA!" in c.out
        assert "pkgb/0.1: WARN: BUILD PKGB!" in c.out


class TestWorkspaceBuild:

    def test_build(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})

        c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_build_msg("BUILD PKGA!"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
               .with_requires("pkga/0.1")})
        c.run("workspace add pkga")
        c.run("workspace add pkgb")
        c.run("workspace build")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild")})
        assert "conanfile.py (pkga/0.1): WARN: BUILD PKGA!" in c.out
        assert "conanfile.py (pkgb/0.1): WARN: BUILD PKGB!" in c.out

        # It is also possible to build a specific package by path
        # equivalent to ``conan build <path> --build=editable``
        # This can be done even if it is not a product
        c.run("workspace build --pkg=pkgc/*", assert_error=True)
        assert "ERROR: There are no selected packages defined in the workspace" in c.out
        c.run("workspace build --pkg=pkgb/*")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild")})
        assert "conanfile.py (pkga/0.1): WARN: BUILD PKGA!" in c.out
        assert "conanfile.py (pkgb/0.1): WARN: BUILD PKGB!" in c.out

        c.run("workspace build --pkg=pkga/*")
        assert "conanfile.py (pkga/0.1): Calling build()" in c.out
        assert "conanfile.py (pkga/0.1): WARN: BUILD PKGA!" in c.out

    def test_error_if_no_products(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})
        c.run("workspace build", assert_error=True)
        assert "ERROR: There are no selected packages defined in the workspace" in c.out

    def test_build_external_missing(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})

        c.save({"mymath/conanfile.py": GenConanfile("mymath", "0.1").with_build_msg("MyMATH!!"),
                "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_build_msg("BUILD PKGA!")
                                                                .with_requires("mymath/0.1"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
               .with_requires("pkga/0.1")})
        c.run("export mymath")
        c.run("workspace add pkga")
        c.run("workspace add pkgb")
        c.run("workspace build", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'mymath/0.1'" in c.out
        c.run("workspace build --build=missing")
        assert "Workspace building external mymath/0.1" in c.out

    def test_build_dynamic_name_version(self):
        conanfile = textwrap.dedent("""\
            from conan import ConanFile
            class MyConan(ConanFile):
                def build(self):
                    self.output.info(f"Building {self.name} AND {self.version}!!!")
            """)
        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def packages(self):
                    result = []
                    for f in os.listdir(self.folder):
                        if os.path.isdir(os.path.join(self.folder, f)):
                            result.append({"path": f, "ref": f"{f}/0.1"})
                    return result
           """)
        c = TestClient(light=True)
        c.save({"conanws.py": workspace,
                "pkga/conanfile.py": conanfile})
        c.run("workspace info")
        assert "pkga/0.1" in c.out
        c.run("workspace build")
        assert "conanfile.py (pkga/0.1): Building pkga AND 0.1!!!" in c.out


class TestNew:
    def test_new(self):
        # Very basic workspace for testing
        c = TestClient(light=True)
        c.run("new workspace")
        assert 'name = "liba"' in c.load("liba/conanfile.py")
        c.run("workspace info")
        assert "liba/0.1" in c.out
        assert "libb/0.1" in c.out
        assert "app1/0.1" in c.out

    def test_new_dep(self):
        c = TestClient(light=True)
        c.run("new workspace -d requires=dep/0.1")
        assert 'self.requires("dep/0.1")' in c.load("liba/conanfile.py")
        assert 'name = "liba"' in c.load("liba/conanfile.py")
        c.run("workspace info")
        assert "liba/0.1" in c.out
        assert "libb/0.1" in c.out
        assert "app1/0.1" in c.out


class TestMeta:
    def test_install(self):
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile()})
        c.run("create dep --name=dep1 --version=0.1")
        c.run("create dep --name=dep2 --version=0.1")
        c.save({"conanws.yml": "",
                "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("dep1/0.1",
                                                                               "dep2/0.1"),
                "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1",
                                                                               "dep1/0.1")},
               clean_first=True)
        c.run("workspace add liba")
        c.run("workspace add libb")
        c.run("workspace super-install -g CMakeDeps -g CMakeToolchain -of=build "
              "--envs-generation=false")
        assert "Packages build order:\n    liba/0.1\n    libb/0.1" in c.out
        assert "Workspace conanws.py not found in the workspace folder, using default" in c.out
        files = os.listdir(os.path.join(c.current_folder, "build"))
        assert "conan_toolchain.cmake" in files
        assert "dep1-config.cmake" in files
        assert "dep2-config.cmake" in files
        assert "liba-config.cmake" not in files
        assert "libb-config.cmake" not in files
        assert "conanbuild.bat" not in files
        assert "conanbuild.sh" not in files

    def test_conanfilews_custom(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace

            class MyWs(ConanFile):
                settings = "arch", "build_type"
                generators = "MSBuildDeps"

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                "conanws.py": conanfilews})
        c.run("workspace add dep")
        c.run("workspace super-install -of=build")
        files = os.listdir(os.path.join(c.current_folder, "build"))
        assert "conandeps.props" in files

    def test_conanfilews_errors(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace
            class MyWs(ConanFile):
                requires = "dep/0.1"

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"conanws.yml": "conanfilews: myconanfilews.py",
                "dep/conanfile.py": GenConanfile("dep", "0.1"),
                "conanws.py": conanfilews})
        c.run("workspace super-install", assert_error=True)
        assert "ERROR: There are no selected packages defined in the workspace" in c.out
        c.run("workspace add dep")
        c.run("workspace super-install", assert_error=True)
        assert "ERROR: Conanfile in conanws.py shouldn't have 'requires'" in c.out

    def test_install_partial(self):
        # If we want to install only some part of the workspace
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile()})
        c.run("create dep --name=dep1 --version=0.1")
        c.run("create dep --name=dep2 --version=0.1")
        c.save({"conanws.yml": "",
                "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("dep1/0.1"),
                "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1"),
                "libc/conanfile.py": GenConanfile("libc", "0.1").with_requires("libb/0.1",
                                                                               "dep2/0.1")},
               clean_first=True)
        c.run("workspace add liba")
        c.run("workspace add libb")
        c.run("workspace add libc")
        for arg in ("--pkg=libb/*", "--pkg=libb/* --pkg=liba/*"):
            c.run(f"workspace super-install {arg} -g CMakeDeps -of=build")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" not in c.out
            assert "libc/0.1" not in c.out
            files = os.listdir(os.path.join(c.current_folder, "build"))
            assert "dep1-config.cmake" in files
            assert "dep2-config.cmake" not in files

    def test_workspace_options(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace
            class MyWs(ConanFile):
                settings = "arch", "build_type"
                options = {"myoption": [1, 2, 3]}
                def generate(self):
                    self.output.info(f"Generating with my option {self.options.myoption}!!!!")

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                "conanws.py": conanfilews})
        c.run("workspace add dep")
        c.run("workspace super-install -of=build")
        assert "conanws.py base project Conanfile: Generating with my option None!!!!" in c.out
        c.run("workspace super-install -of=build -o *:myoption=1")
        assert "conanws.py base project Conanfile: Generating with my option 1!!!!" in c.out

    def test_workspace_common_shared_options(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace
            class MyWs(ConanFile):
                settings = "os"
                options = {"shared": [True, False],
                           "fPIC": [True, False]}
                default_options = {"shared": False, "fPIC": True}
                implements = "auto_shared_fpic"

                def generate(self):
                    self.output.info(f"OS={self.settings.os}!!!!")
                    self.output.info(f"shared={self.options.shared}!!!!")
                    self.output.info(f"fPIC={self.options.get_safe('fPIC')}!!!!")

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                "conanws.py": conanfilews})
        c.run("workspace add dep")
        c.run("workspace super-install -of=build -s os=Windows")
        assert "conanws.py base project Conanfile: OS=Windows!!!!" in c.out
        assert "conanws.py base project Conanfile: shared=False!!!!" in c.out
        assert "conanws.py base project Conanfile: fPIC=None!!!!" in c.out
        c.run("workspace super-install -of=build -s os=Linux -o *:shared=True")
        assert "conanws.py base project Conanfile: OS=Linux!!!!" in c.out
        assert "conanws.py base project Conanfile: shared=True!!!!" in c.out
        assert "conanws.py base project Conanfile: fPIC=None!!!!" in c.out
        c.run("workspace super-install -of=build -s os=Linux -o *:shared=False")
        assert "conanws.py base project Conanfile: OS=Linux!!!!" in c.out
        assert "conanws.py base project Conanfile: shared=False!!!!" in c.out
        assert "conanws.py base project Conanfile: fPIC=True!!!!" in c.out

    def test_workspace_pkg_options(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace

            class MyWs(ConanFile):
                settings = "arch", "build_type"
                def generate(self):
                    for pkg, options in self.workspace_packages_options.items():
                        for k, v in options.items():
                            self.output.info(f"Generating with opt {pkg}:{k}={v}!!!!")

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_option("myoption", [1, 2, 3]),
                "conanws.py": conanfilews})
        c.run("workspace add dep")
        c.run("workspace super-install -of=build")
        assert "project Conanfile: Generating with opt dep/0.1:myoption=None!!!!" in c.out
        c.run("workspace super-install -of=build -o *:myoption=1")
        assert "project Conanfile: Generating with opt dep/0.1:myoption=1!!!!" in c.out


def test_workspace_with_local_recipes_index():
    c3i_folder = temp_folder()
    recipes_folder = os.path.join(c3i_folder, "recipes")
    zlib_config = textwrap.dedent("""
       versions:
         "1.2.11":
           folder: all
       """)
    save_files(recipes_folder, {"zlib/config.yml": zlib_config,
                                "zlib/all/conanfile.py": str(GenConanfile("zlib")),
                                "zlib/all/conandata.yml": ""})

    c = TestClient(light=True)
    c.save({".conanrc": 'conan_home=deps\n'})
    c.run(f'remote add local "{c3i_folder}"')

    c.run("list zlib/1.2.11#* -r=local")
    assert "zlib/1.2.11" in c.out  # It doesn't crash
    c.run("list zlib/1.2.11#*")
    assert "zlib/1.2.11" not in c.out


class TestClean:
    def test_clean(self):
        # Using cmake_layout, we can clean the build folders
        c = TestClient()
        c.save({"conanws.yml": "name: my_workspace"})
        pkga = GenConanfile("pkga", "0.1").with_settings("build_type")
        pkgb = GenConanfile("pkgb", "0.1").with_requires("pkga/0.1").with_settings("build_type")
        c.save({"pkga/conanfile.py": pkga ,
                "pkgb/conanfile.py": pkgb,
                "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1")})
        c.run("workspace add pkga -of=build/pkga")
        c.run("workspace add pkgb -of=build/pkgb")
        c.run("workspace add pkgc")
        c.run("workspace build")
        assert os.path.exists(os.path.join(c.current_folder, "build", "pkga"))
        assert os.path.exists(os.path.join(c.current_folder, "build", "pkgb"))
        c.run("workspace clean")
        assert "Workspace 'my_workspace': Removing pkga/0.1 output folder" in c.out
        assert "Workspace 'my_workspace': Removing pkgb/0.1 output folder" in c.out
        assert "Editable pkgc/0.1 doesn't have an output_folder defined" in c.out
        assert not os.path.exists(os.path.join(c.current_folder, "build", "pkga"))
        assert not os.path.exists(os.path.join(c.current_folder, "build", "pkgb"))

    def test_custom_clean(self):
        conanfilews = textwrap.dedent("""
            from conan import Workspace

            class Ws(Workspace):
                def name(self):
                    return "my_workspace"
                def clean(self):
                    self.output.info("MY CLEAN!!!!")
            """)
        c = TestClient()
        c.save({"conanws.py": conanfilews})
        c.run("workspace clean")
        assert "Workspace 'my_workspace': MY CLEAN!!!" in c.out


def test_relative_paths():
    # This is using the meta-project
    c = TestClient()
    c.run("new cmake_lib -d name=liba --output=liba")
    c.run("new cmake_exe -d name=app1 -d requires=liba/0.1 --output=app1")
    c.run("new cmake_lib -d name=libb --output=other/libb")
    c.run("new cmake_exe -d name=app2 -d requires=libb/0.1 --output=other/app2")
    c.run("workspace init mywks")
    c.run("workspace init otherwks")
    # cd mywks
    with c.chdir("mywks"):
        c.run("workspace add ../liba")
        c.run("workspace add ../app1")
        c.run("workspace info")
        expected = textwrap.dedent("""\
        packages
          - path: ../liba
            ref: liba/0.1
          - path: ../app1
            ref: app1/0.1
        """)
        assert expected in c.out
        c.run("graph info --requires=app1/0.1")
        c.assert_listed_require({"app1/0.1": "Editable", "liba/0.1": "Editable"})
    # cd otherwks
    with c.chdir("otherwks"):
        c.run("workspace add ../other/libb")
        c.run("workspace add ../other/app2")
        c.run("workspace info")
        expected = textwrap.dedent("""\
        packages
          - path: ../other/libb
            ref: libb/0.1
          - path: ../other/app2
            ref: app2/0.1
        """)
        assert expected in c.out
        c.run("graph info --requires=app2/0.1")
        c.assert_listed_require({"app2/0.1": "Editable", "libb/0.1": "Editable"})


def test_host_build_require():
    c = TestClient()
    protobuf = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.files import save, copy
        class Protobuf(ConanFile):
            name = "protobuf"
            version = "0.1"
            settings = "os"

            def layout(self):
                self.folders.build = f"mybuild/folder_{self.settings.os}"
                self.cpp.build.bindirs = ["."]

            def build(self):
                save(self, "myprotobuf.txt", f"MYOS={self.settings.os}!!!")

            def package(self):
                copy(self, "myprotobuf.txt", src=self.build_folder, dst=self.package_folder)

            def package_info(self):
                self.cpp_info.bindirs = ["."]
        """)
    app = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Protobuf(ConanFile):
            name = "app"
            version = "0.1"
            requires = "protobuf/0.1"
            tool_requires = "protobuf/0.1"

            def build(self):
                binhost = self.dependencies.host["protobuf"].cpp_info.bindir
                binbuild = self.dependencies.build["protobuf"].cpp_info.bindir
                host = load(self, os.path.join(binhost, "myprotobuf.txt"))
                build = load(self, os.path.join(binbuild, "myprotobuf.txt"))
                self.output.info(f"BUILDING WITH BINHOST: {host}")
                self.output.info(f"BUILDING WITH BINBUILD: {build}")
        """)
    c.save({"protobuf/conanfile.py": protobuf,
            "app/conanfile.py": app})
    c.run("workspace init .")
    c.run("workspace add protobuf")
    c.run("workspace add app")
    c.run("install app --build=editable -s:b os=Linux -s:h os=Windows")

    assert c.load("protobuf/mybuild/folder_Linux/myprotobuf.txt") == "MYOS=Linux!!!"
    assert c.load("protobuf/mybuild/folder_Windows/myprotobuf.txt") == "MYOS=Windows!!!"

    shutil.rmtree(os.path.join(c.current_folder, "protobuf", "mybuild"))
    assert not os.path.exists(os.path.join(c.current_folder, "protobuf", "mybuild"))
    c.run("workspace build -s:b os=Linux -s:h os=Windows")
    assert "conanfile.py (app/0.1): BUILDING WITH BINHOST: MYOS=Windows!!!" in c.out
    assert "conanfile.py (app/0.1): BUILDING WITH BINBUILD: MYOS=Linux!!!" in c.out
    assert c.load("protobuf/mybuild/folder_Linux/myprotobuf.txt") == "MYOS=Linux!!!"
    assert c.load("protobuf/mybuild/folder_Windows/myprotobuf.txt") == "MYOS=Windows!!!"

    shutil.rmtree(os.path.join(c.current_folder, "protobuf", "mybuild"))
    assert not os.path.exists(os.path.join(c.current_folder, "protobuf", "mybuild"))
    c.run("workspace create -s:b os=Linux -s:h os=Windows")
    assert "app/0.1: BUILDING WITH BINHOST: MYOS=Windows!!!" in c.out
    assert "app/0.1: BUILDING WITH BINBUILD: MYOS=Linux!!!" in c.out


class TestCreate:
    def test_create(self):
        c = TestClient(light=True, default_server_user=True)
        c.save({"conanfile.py": GenConanfile("zlib", "0.1").with_build_msg("BUILD ZLIB!")})
        c.run("export .")
        c.save({"conanws.yml": ""}, clean_first=True)
        c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_requires("zlib/0.1")
                                                                .with_build_msg("BUILD PKGA!"),
                "pkga/test_package/conanfile.py": GenConanfile().with_test("pass"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
               .with_requires("pkga/0.1"),
                "pkgb/test_package/conanfile.py": GenConanfile().with_test("pass"),
                "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_build_msg("BUILD PKGC!")
               .with_requires("pkgb/0.1"),
                "pkgc/test_package/conanfile.py": GenConanfile().with_test("pass"),
                })
        c.run("workspace add pkga")
        c.run("workspace add pkgb")
        c.run("workspace add pkgc")
        c.run("workspace create --build=zlib/*")
        assert str(c.out).count("zlib/0.1: WARN: BUILD ZLIB!") == 1
        assert str(c.out).count("pkga/0.1: WARN: BUILD PKGA!") == 1
        assert str(c.out).count("pkgb/0.1: WARN: BUILD PKGB!") == 1
        assert str(c.out).count("pkgc/0.1: WARN: BUILD PKGC!") == 1
        assert "pkga/0.1 (test package): Running test()" in c.out
        assert "pkgb/0.1 (test package): Running test()" in c.out
        assert "pkgc/0.1 (test package): Running test()" in c.out

        # A second conan workspace create will not re-build
        c.run("workspace create")
        assert "WARN: BUILD ZLIB!" not in c.out
        assert "WARN: BUILD PKGA!" not in c.out
        assert "WARN: BUILD PKGB!" not in c.out
        assert "WARN: BUILD PKBC!" not in c.out
        assert "pkga/0.1 (test package): Running test()" not in c.out
        assert "pkgb/0.1 (test package): Running test()" not in c.out
        assert "pkgc/0.1 (test package): Running test()" not in c.out

        c.run("upload zlib/* -r=default -c")
        c.run("remove zlib/* -c")
        c.run("remove pkgc/* -c")
        c.run("workspace create")
        assert "WARN: BUILD ZLIB!" not in c.out
        assert "pkgc/0.1: WARN: BUILD PKGC!" in c.out


    def test_create_dynamic_name(self):
        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def packages(self):
                    result = []
                    for f in os.listdir(self.folder):
                        if os.path.isdir(os.path.join(self.folder, f)):
                            result.append({"path": f, "ref": f"{f}/0.1"})
                    return result
           """)
        c = TestClient(light=True)
        c.save({"conanws.py": workspace,
                "pkga/conanfile.py": GenConanfile()})
        c.run("workspace info")
        assert "pkga/0.1" in c.out
        c.run("workspace create")
        assert "Workspace create pkga/0.1" in c.out


    def test_host_build_require(self):
        c = TestClient()
        protobuf = textwrap.dedent("""\
            from conan import ConanFile
            class Protobuf(ConanFile):
                name = "protobuf"
                version = "0.1"
                settings = "os"

                def build(self):
                    self.output.info(f"Building for: {self.settings.os}!!!")
            """)
        app = textwrap.dedent("""\
            from conan import ConanFile
            class Protobuf(ConanFile):
                name = "app"
                version = "0.1"
                requires = "protobuf/0.1"
                tool_requires = "protobuf/0.1"
            """)
        c.save({"protobuf/conanfile.py": protobuf,
                "app/conanfile.py": app})
        c.run("workspace init .")
        c.run("workspace add protobuf")
        c.run("workspace add app")

        c.run("workspace create -s:b os=Linux -s:h os=Windows")

        assert "protobuf/0.1: Building for: Windows!!!" in c.out
        assert "protobuf/0.1: Building for: Linux!!!" in c.out


class TestSource:
    def test_source(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})

        pkga = textwrap.dedent("""\
            from conan import ConanFile
            class TestPackage(ConanFile):
                name = "pkga"
                version = "0.1"
                def source(self):
                    self.output.info("Executing SOURCE!!!")
            """)
        pkgb = textwrap.dedent("""\
            from conan import ConanFile
            class TestPackage(ConanFile):
                name = "pkgb"
                version = "0.1"
                requires = "pkga/0.1"
                def source(self):
                    self.output.info("Executing SOURCE!!!")
            """)
        pkgc = textwrap.dedent("""\
            from conan import ConanFile
            class TestPackage(ConanFile):
                name = "pkgc"
                version = "0.1"
                requires = "pkgb/0.1"
                def source(self):
                    self.output.info("Executing SOURCE!!!")
            """)
        c.save({"pkga/conanfile.py": pkga,
                "pkgb/conanfile.py": pkgb,
                "pkgc/conanfile.py": pkgc})
        c.run("workspace add pkga")
        c.run("workspace add pkgb")
        c.run("workspace add pkgc")
        c.run("workspace source")
        assert "conanfile.py (pkga/0.1): Executing SOURCE!!!" in c.out
        assert "conanfile.py (pkgb/0.1): Executing SOURCE!!!" in c.out
        assert "conanfile.py (pkgc/0.1): Executing SOURCE!!!" in c.out


class TestInstall:
    def test_install(self):
        c = TestClient()
        c.save({"conanws.yml": ""})

        pkg = textwrap.dedent("""\
            from conan import ConanFile
            class Package(ConanFile):
                name = "{}"
                version = "0.1"
                settings = "os", "build_type"
                {}
                generators = "CMakeToolchain"
            """)

        c.save({"pkga/conanfile.py": pkg.format("pkga", ''),
                "pkgb/conanfile.py": pkg.format("pkgb", 'requires="pkga/0.1"'),
                "pkgc/conanfile.py": pkg.format("pkgc", 'requires="pkgb/0.1"')})
        c.run("workspace add pkga")
        c.run("workspace add pkgb")
        c.run("workspace add pkgc")
        c.run("workspace install")
        assert "conanfile.py (pkga/0.1): CMakeToolchain generated" in c.out
        assert "conanfile.py (pkgb/0.1): CMakeToolchain generated" in c.out
        assert "conanfile.py (pkgc/0.1): CMakeToolchain generated" in c.out


def test_keep_core_conf():
    c = TestClient()
    myprofile = textwrap.dedent("""\
        [settings]
        os=FreeBSD
        arch=armv7
        """)
    conanfile = textwrap.dedent("""\
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkga"
            version = "0.1"
            settings = "os", "arch"

            def generate(self):
                self.output.info(f"Generating!: {self.settings.os}-{self.settings.arch}!!!!")
        """)
    c.save_home({"profiles/myprofile": myprofile})
    c.run("profile show ")
    c.save({"conanws.yml": "",
            "pkga/conanfile.py": conanfile})
    c.run("workspace add pkga")
    # The injected -cc is still applied to every "conan install"
    c.run("workspace install -cc core:default_profile=myprofile")
    assert "conanfile.py (pkga/0.1): Generating!: FreeBSD-armv7!!!!" in c.out
    # also the global.conf
    c.save_home({"global.conf": "core:default_profile=myprofile"})
    c.run("workspace install")
    assert "conanfile.py (pkga/0.1): Generating!: FreeBSD-armv7!!!!" in c.out


def test_workspace_defining_only_paths():
    c = TestClient()
    c.run("new workspace")
    conanws_with_labels = textwrap.dedent("""\
    packages:
      - path: liba
      - path: libb
      - path: app1
    """)
    c.save({"conanws.yml": conanws_with_labels})
    # liba with user and channel too
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "liba", "conanfile.py"),
                    'version = "0.1"',
                    'version = "0.1"\n    user = "myuser"\n    channel = "mychannel"')
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "libb", "conanfile.py"),
                    'self.requires("liba/0.1")',
                    'self.requires("liba/0.1@myuser/mychannel")')
    c.run("workspace info")
    expected = textwrap.dedent("""\
    packages
      - path: liba
      - path: libb
      - path: app1
    """)
    assert expected in c.out
    c.run("workspace install")
    assert "conanfile.py (app1/0.1)" in c.out
    assert "liba/0.1@myuser/mychannel - Editable" in c.out
    assert "libb/0.1 - Editable" in c.out


def test_workspace_defining_duplicate_references():
    """
    Testing duplicate references but different paths
    """
    c = TestClient()
    conanws_with_labels = textwrap.dedent("""\
    packages:
      - path: liba
      - path: liba1
      - path: liba2
    """)
    c.save({
        "conanws.yml": conanws_with_labels,
        "liba/conanfile.py": GenConanfile(name="liba", version="0.1"),
        "liba1/conanfile.py": GenConanfile(name="liba", version="0.1"),
        "liba2/conanfile.py": GenConanfile(name="liba", version="0.1"),
    })
    c.run("workspace install", assert_error=True)
    assert "Workspace editable reference 'liba/0.1' already exists." in c.out


def test_workspace_reference_error():
    c = TestClient()
    conanws_with_labels = textwrap.dedent("""\
    packages:
      - path: libx
    """)
    c.save({"conanws.yml": conanws_with_labels,
            "libx/conanfile.py": ""})
    c.run("workspace install", assert_error=True)
    assert ("Workspace editable reference could not be deduced by libx/conanfile.py or it is not"
            " correctly defined in the conanws.yml file.") in c.out
