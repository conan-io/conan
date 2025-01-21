import json
import os
import textwrap

import pytest

from conan.internal.workspace import Workspace
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save

Workspace.TEST_ENABLED = "will_break_next"


class TestHomeRoot:
    @pytest.mark.parametrize("ext, content", [("py", "home_folder = 'myhome'"),
                                              ("yml", "home_folder: myhome")])
    def test_workspace_home(self, ext, content):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        save(os.path.join(folder, f"conanws.{ext}"), content)
        c = TestClient(current_folder=cwd, light=True)
        c.run("config home")
        assert os.path.join(folder, "myhome") in c.stdout

    def test_workspace_home_user_py(self):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        conanwspy = textwrap.dedent("""
            def home_folder():
                return "new" + conanws_data["home_folder"]
            """)
        save(os.path.join(folder, f"conanws.py"), conanwspy)
        save(os.path.join(folder, "conanws.yml"), "home_folder: myhome")
        c = TestClient(current_folder=cwd, light=True)
        c.run("config home")
        assert os.path.join(folder, "newmyhome") in c.stdout

    def test_workspace_root(self):
        c = TestClient(light=True)
        # Just check the root command works
        c.run("workspace root", assert_error=True)
        assert "ERROR: No workspace defined, conanws.py file not found" in c.out
        c.save({"conanws.py": ""})
        c.run("workspace root")
        assert c.current_folder in c.stdout

        c.save({"conanws.yml": ""}, clean_first=True)
        c.run("workspace root")
        assert c.current_folder in c.stdout


class TestAddRemove:

    def test_add(self):
        c = TestClient(light=True)
        c.save({"conanws.py": "name='myws'",
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
        c.save({"sub/conanws.py": "name='myws'",
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
                name = "myws"

                workspace_folder = os.path.dirname(os.path.abspath(__file__))

                def editables():
                    result = {}
                    for f in os.listdir(workspace_folder):
                        if os.path.isdir(os.path.join(workspace_folder, f)):
                            name = open(os.path.join(workspace_folder, f, "name.txt")).read().strip()
                            version = open(os.path.join(workspace_folder, f,
                                                        "version.txt")).read().strip()
                            p = os.path.join(f, "conanfile.py").replace("\\\\", "/")
                            result[f"{name}/{version}"] = {"path": p}
                    return result
                """)
        else:
            workspace = textwrap.dedent("""\
               import os
               name = "myws"

               def editables(*args, **kwargs):
                   result = {}
                   for f in os.listdir(workspace_api.folder):
                       if os.path.isdir(os.path.join(workspace_api.folder, f)):
                           f = os.path.join(f, "conanfile.py").replace("\\\\", "/")
                           conanfile = workspace_api.load(f)
                           result[f"{conanfile.name}/{conanfile.version}"] = {"path": f}
                   return result
               """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile,
                "dep1/name.txt": "pkg",
                "dep1/version.txt": "2.1"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"pkg/2.1": {"path": "dep1/conanfile.py"}}
        c.save({"dep1/name.txt": "other",
                "dep1/version.txt": "14.5"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"other/14.5": {"path": "dep1/conanfile.py"}}
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
           name = "myws"

           def editables(*args, **kwargs):
               conanfile = workspace_api.load("dep1/conanfile.py")
               return {f"{conanfile.name}/{conanfile.version}": {"path": "dep1/conanfile.py"}}
            """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"pkg/2.1": {"path": "dep1/conanfile.py"}}

    def test_error_uppercase(self):
        c = TestClient(light=True)
        c.save({"conanws.py": "name='myws'",
                "conanfile.py": GenConanfile("Pkg", "0.1")})
        c.run("workspace add .", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out
        c.save({"conanfile.py": GenConanfile()})
        c.run("workspace add . --name=Pkg --version=0.1", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out

    def test_add_open_error(self):
        c = TestClient(light=True)
        c.save({"conanws.py": "name='myws'",
                "dep/conanfile.py": GenConanfile("dep", "0.1")})
        c.run("workspace add dep")
        c.run("workspace open dep/0.1", assert_error=True)
        assert "ERROR: Can't open a dependency that is already an editable: dep/0.1" in c.out


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
        c2.save({"conanws.py": ""})
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
        c2.save({"conanws.py": ""})
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
