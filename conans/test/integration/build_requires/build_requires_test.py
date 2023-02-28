import os
import platform
import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized

from conan.tools.env.environment import environment_wrap_command
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile


@pytest.fixture()
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "build_type"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.build_type)
                    save(self, "bin/myopenssl.bat", echo)
                    save(self, "bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            type = "application"
            settings = "build_type"
            def requirements(self):
                self.requires("openssl/1.0", run=True)
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.build_type)
                    save(self, "mycmake.bat", echo + "\ncall myopenssl.bat")
                    save(self, "mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
                self.buildenv_info.define("MYCMAKEVAR", "MYCMAKEVALUE!!")
            """)

    gtest = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "build_type"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYGTEST={}!!".format(self.settings.build_type)
                    save(self, "bin/mygtest.bat", echo)
                    save(self, "bin/mygtest.sh", echo)
                    os.chmod("bin/mygtest.sh", 0o777)

            def package_info(self):
                self.runenv_info.define("MYGTESTVAR",
                                        "MyGTestValue{}".format(self.settings.build_type))
            """)
    client = TestClient()
    client.save({"cmake/conanfile.py": cmake,
                 "gtest/conanfile.py": gtest,
                 "openssl/conanfile.py": openssl})

    client.run("create openssl --name=openssl --version=1.0")
    client.run("create cmake --name=mycmake --version=1.0")
    client.run("create gtest --name=mygtest --version=1.0")

    myrunner_bat = "@echo off\necho MYGTESTVAR=%MYGTESTVAR%!!\n"
    myrunner_sh = "echo MYGTESTVAR=$MYGTESTVAR!!\n"
    client.save({"myrunner.bat": myrunner_bat,
                 "myrunner.sh": myrunner_sh}, clean_first=True)
    os.chmod(os.path.join(client.current_folder, "myrunner.sh"), 0o777)
    return client


def test_conanfile_txt(client):
    # conanfile.txt -(br)-> cmake
    client.save({"conanfile.txt": "[tool_requires]\nmycmake/1.0"}, clean_first=True)
    client.run("install . -s:h build_type=Debug")

    assert "mycmake/1.0" in client.out
    assert "openssl/1.0" in client.out
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command("conanbuild", client.current_folder, "mycmake.{}".format(ext))
    client.run_command(cmd)

    assert "MYCMAKE=Release!!" in client.out
    assert "MYOPENSSL=Release!!" in client.out


def test_complete(client):
    app = textwrap.dedent("""
        import platform
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            build_requires = "mycmake/1.0"
            settings = "os"

            def build_requirements(self):
                self.test_requires("mygtest/1.0", run=True)

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)
                mytest_cmd = "mygtest.bat" if platform.system() == "Windows" else "mygtest.sh"
                self.run(mytest_cmd, env="conanrun")
       """)

    client.save({"conanfile.py": app})
    client.run("install . -s build_type=Debug --build=missing")
    # Run the BUILD environment
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command("conanbuild", client.current_folder,
                                   cmd="mycmake.{}".format(ext))
    client.run_command(cmd)
    assert "MYCMAKE=Release!!" in client.out
    assert "MYOPENSSL=Release!!" in client.out

    # Run the RUN environment
    cmd = environment_wrap_command("conanrun", client.current_folder,
                                   cmd="mygtest.{ext} && .{sep}myrunner.{ext}".format(ext=ext,
                                                                                      sep=os.sep))
    client.run_command(cmd)
    assert "MYGTEST=Debug!!" in client.out
    assert "MYGTESTVAR=MyGTestValueDebug!!" in client.out

    client.run("build . -s:h build_type=Debug")
    assert "MYCMAKE=Release!!" in client.out
    assert "MYOPENSSL=Release!!" in client.out
    assert "MYGTEST=Debug!!" in client.out


tool_conanfile = """from conan import ConanFile

class Tool(ConanFile):
    name = "Tool"
    version = "0.1"

    def package_info(self):
        self.buildenv_info.define_path("TOOL_PATH", "MyToolPath")
"""

tool_conanfile2 = tool_conanfile.replace("0.1", "0.3")

conanfile = """
import os
from conan import ConanFile, tools
from conan.tools.env import VirtualBuildEnv

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    {}

    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("ToolPath: %s" % os.getenv("TOOL_PATH"))
"""

requires = conanfile.format('build_requires = "Tool/0.1@lasote/stable"')
requires_range = conanfile.format('build_requires = "Tool/[>0.0]@lasote/stable"')
requirements = conanfile.format("""def build_requirements(self):
        self.build_requires("Tool/0.1@lasote/stable")""")
override = conanfile.format("""build_requires = "Tool/0.2@user/channel"

    def build_requirements(self):
        self.build_requires("Tool/0.1@lasote/stable")""")


profile = """
[tool_requires]
Tool/0.3@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""


@pytest.mark.xfail(reason="Legacy tests with wrong propagation asumptions")
class BuildRequiresTest(unittest.TestCase):

    def test_consumer(self):
        # https://github.com/conan-io/conan/issues/5425
        catch_ref = RecipeReference.loads("catch/0.1@user/testing")
        libA_ref = RecipeReference.loads("LibA/0.1@user/testing")

        t = TestClient()
        t.save({"conanfile.py":
                    GenConanfile().with_package_info(cpp_info={"libs": ["mylibcatch0.1lib"]},
                                                     env_info={"MYENV": ["myenvcatch0.1env"]})})
        t.run("create . --name=catch --version=0.1 --user=user --channel=testing")
        t.save({"conanfile.py": GenConanfile().with_requirement(catch_ref, private=True)})
        t.run("create . --name=LibA --version=0.1 --user=user --channel=testing")
        t.save({"conanfile.py": GenConanfile().with_require(libA_ref)
                                              .with_tool_requires(catch_ref)})
        t.run("install .")
        self.assertIn("catch/0.1@user/testing from local cache", t.out)
        self.assertIn("catch/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip",
                      t.out)
        self.assertIn("catch/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      t.out)

    def test_build_requires_diamond(self):
        libA_ref = RecipeReference.loads("liba/0.1@user/testing")
        libB_ref = RecipeReference.loads("libb/0.1@user/testing")

        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("create . --name=liba --version=0.1 --user=user --channel=testing")

        t.save({"conanfile.py": GenConanfile().with_require(libA_ref)})
        t.run("create . --name=libb --version=0.1 --user=user --channel=testing")

        t.save({"conanfile.py": GenConanfile().with_tool_requires(libB_ref)
                                              .with_tool_requires(libA_ref)})
        t.run("create . --name=libC --version=0.1 --user=user --channel=testing")
        self.assertIn("libC/0.1@user/testing: Created package", t.out)

    def test_create_with_tests_and_build_requires(self):
        client = TestClient()
        # Generate and export the build_require recipe
        conanfile1 = """from conan import ConanFile
class MyBuildRequire(ConanFile):
    def package_info(self):
        self.buildenv_info.define("MYVAR", "1")
"""
        client.save({"conanfile.py": conanfile1})
        client.run("create . --name=Build1 --version=0.1 --user=conan --channel=stable")
        conanfile2 = """from conan import ConanFile
class MyBuildRequire(ConanFile):
    def package_info(self):
        self.buildenv_info.define("MYVAR2", "2")
"""
        client.save({"conanfile.py": conanfile2})
        client.run("create . --name=Build2 --version=0.1 --user=conan --channel=stable")

        # Create a recipe that will use a profile requiring the build_require
        client.save({"conanfile.py": """
from conan.tools.env import VirtualBuildEnv
from conan import ConanFile
import os

class MyLib(ConanFile):
    build_requires = "Build2/0.1@conan/stable"
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert(os.environ['MYVAR']=='1')
            assert(os.environ['MYVAR2']=='2')

""", "myprofile": '''
[tool_requires]
Build1/0.1@conan/stable
''',
                    "test_package/conanfile.py": """from conan import ConanFile
import os
from conan.tools.env import VirtualBuildEnv
class MyTest(ConanFile):
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert(os.environ['MYVAR']=='1')
    def test(self):
        self.output.info("TESTING!!!")
"""}, clean_first=True)

        # Test that the build require is applyed to testing
        client.run("create . --name=Lib --version=0.1 --user=conan/stable --profile=. --channel=myprofile")
        self.assertEqual(1, str(client.out).count("Lib/0.1@conan/stable: "
                                                  "Applying build-requirement:"
                                                  " Build1/0.1@conan/stable"))
        self.assertIn("TESTING!!", client.out)

    def test_dependents(self):
        client = TestClient()
        boost = """from conan import ConanFile
class Boost(ConanFile):
    def package_info(self):
        self.buildenv_info.define_path("PATH", "myboostpath")
"""
        client.save({CONANFILE: boost})
        client.run("create . --name=Boost --version=1.0 --user=user --channel=channel")
        other = """[tool_requires]
Boost/1.0@user/channel
"""
        client.save({"conanfile.txt": other}, clean_first=True)
        client.run("install .")

        self.assertIn("""Build requirements
    Boost/1.0@user/channel""", client.out)

        other = """from conan import ConanFile
import os
class Other(ConanFile):
    requires = "Boost/1.0@user/channel"
    def build(self):
        self.output.info("OTHER PATH FOR BUILD %s" % os.getenv("PATH"))
    def package_info(self):
        self.env_info.PATH.append("myotherpath")
"""
        client.save({CONANFILE: other})
        client.run("create . --name=other --version=1.0 --user=user --channel=channel")
        lib = """from conan import ConanFile
import os
class Lib(ConanFile):
    build_requires = "boost/1.0@user/channel", "other/1.0@user/channel"
    def build(self):
        self.output.info("LIB PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: lib})
        client.run("create . --name=Lib --version=1.0 --user=user --channel=channel")
        self.assertIn("LIB PATH FOR BUILD myotherpath%smyboostpath" % os.pathsep,
                      client.out)

    def test_applyname(self):
        # https://github.com/conan-io/conan/issues/4135
        client = TestClient()
        mingw = """from conan import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.define_path("PATH", "mymingwpath")
"""
        myprofile = """
[tool_requires]
consumer*: mingw/0.1@myuser/stable
"""
        app = """from conan import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class App(ConanFile):
    name = "consumer"
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("APP PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . --name=mingw --version=0.1 --user=myuser --channel=stable")
        client.save({CONANFILE: app,
                     "myprofile": myprofile})
        client.run("build . -pr=myprofile")
        self.assertIn("conanfile.py (consumer/None): Applying build-requirement: "
                      "mingw/0.1@myuser/stable", client.out)
        self.assertIn("conanfile.py (consumer/None): APP PATH FOR BUILD mymingwpath",
                      client.out)

    def test_transitive(self):
        client = TestClient()
        mingw = """from conan import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.append("MYVAR", "mymingwpath")
"""
        myprofile = """
[tool_requires]
mingw/0.1@lasote/stable
"""
        gtest = """from conan import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class Gtest(ConanFile):
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("GTEST PATH FOR BUILD %s" % os.getenv("MYVAR"))
"""
        app = """from conan import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class App(ConanFile):
    build_requires = "gtest/0.1@lasote/stable"
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("APP PATH FOR BUILD %s" % os.getenv("MYVAR"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . --name=mingw --version=0.1 --user=lasote --channel=stable")
        client.save({CONANFILE: gtest})
        client.run("export . --name=gtest --version=0.1 --user=lasote --channel=stable")
        client.save({CONANFILE: app,
                     "myprofile": myprofile})
        client.run("create . --name=app --version=0.1 --user=lasote --channel=stable --build=missing -pr=myprofile -pr:b=myprofile")
        self.assertIn("app/0.1@lasote/stable: APP PATH FOR BUILD mymingwpath",
                      client.out)
        self.assertIn("gtest/0.1@lasote/stable: GTEST PATH FOR BUILD mymingwpath",
                      client.out)

    def test_profile_order(self):
        client = TestClient()
        mingw = """from conan import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.append("MYVAR", "mymingwpath")
"""
        msys = """from conan import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.append("MYVAR", "mymsyspath")
"""
        myprofile1 = """
[tool_requires]
mingw/0.1@lasote/stable
msys/0.1@lasote/stable
"""
        myprofile2 = """
[tool_requires]
msys/0.1@lasote/stable
mingw/0.1@lasote/stable
"""

        app = """from conan import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class App(ConanFile):
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("FOR BUILD %s" % os.getenv("MYVAR"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . --name=mingw --version=0.1 --user=lasote --channel=stable")
        client.save({CONANFILE: msys})
        client.run("create . --name=msys --version=0.1 --user=lasote --channel=stable")
        client.save({CONANFILE: app,
                     "myprofile1": myprofile1,
                     "myprofile2": myprofile2})
        client.run("create . --name=app --version=0.1 --user=lasote --channel=stable -pr=myprofile1")
        # mingw being the first one, has priority and its "append" mandates it is the last appended
        self.assertIn("app/0.1@lasote/stable: FOR BUILD mymsyspath mymingwpath", client.out)
        client.run("create . --name=app --version=0.1 --user=lasote --channel=stable -pr=myprofile2")
        self.assertIn("app/0.1@lasote/stable: FOR BUILD mymingwpath mymsyspath", client.out)

    def test_require_itself(self):
        client = TestClient()
        mytool_conanfile = """from conan import ConanFile
class Tool(ConanFile):
    def build(self):
        self.output.info("BUILDING MYTOOL")
"""
        myprofile = """
[tool_requires]
Tool/0.1@lasote/stable
"""
        client.save({CONANFILE: mytool_conanfile,
                     "profile.txt": myprofile})
        client.run("create . --name=Tool --version=0.1 --user=lasote --channel=stable -pr=profile.txt")
        self.assertEqual(1, str(client.out).count("BUILDING MYTOOL"))

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_build_requires(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile})
        client.run("export . --user=lasote --channel=stable")

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

        client.run("install --requires=MyLib/0.1@lasote/stable --build missing")
        self.assertIn("Tool/0.1@lasote/stable: Generating the package", client.out)
        self.assertIn("ToolPath: MyToolPath", client.out)

        client.run("install --requires=MyLib/0.1@lasote/stable")
        self.assertNotIn("Tool", client.out)
        self.assertIn("MyLib/0.1@lasote/stable: Already installed!", client.out)

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_profile_override(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile2}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

        client.save({CONANFILE: conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile.replace("0.3", "[>0.2]")}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

        client.run("install --requires=MyLib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertNotIn("Tool/0.1", client.out)
        self.assertNotIn("Tool/0.2", client.out)
        self.assertIn("Tool/0.3@lasote/stable: Generating the package", client.out)
        self.assertIn("ToolPath: MyToolPath", client.out)

        client.run("install --requires=MyLib/0.1@lasote/stable")
        self.assertNotIn("Tool", client.out)
        self.assertIn("MyLib/0.1@lasote/stable: Already installed!", client.out)

        client.run("install --requires=MyLib/0.1@lasote/stable --profile ./profile2.txt --build")
        self.assertNotIn("Tool/0.1", client.out)
        self.assertNotIn("Tool/0.2", client.out)
        self.assertIn("Tool/0.3@lasote/stable: Generating the package", client.out)
        self.assertIn("ToolPath: MyToolPath", client.out)

    def test_options(self):
        conanfile = """from conan import ConanFile
class package(ConanFile):
    name            = "first"
    version         = "0.0.0"
    options         = {"coverage": [True, False]}
    default_options = {"coverage": False}
    def build(self):
        self.output.info("Coverage: %s" % self.options.coverage)
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . --user=lasote --channel=stable")

        consumer = """from conan import ConanFile

class package(ConanFile):
    name            = "second"
    version         = "0.0.0"
    default_options = {"first:coverage": True}
    build_requires  = "first/0.0.0@lasote/stable"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --build=missing -o Pkg/*:someoption=3")
        self.assertIn("first/0.0.0@lasote/stable: Coverage: True", client.out)

    def test_failed_assert(self):
        # https://github.com/conan-io/conan/issues/5685
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=common --version=1.0 --user=test --channel=test")

        req = textwrap.dedent("""
            from conan import ConanFile
            class BuildReqConan(ConanFile):
                requires = "common/1.0@test/test"
            """)
        client.save({"conanfile.py": req})
        client.run("export . --name=req --version=1.0 --user=test --channel=test")
        client.run("export . --name=build_req --version=1.0 --user=test --channel=test")

        build_req_req = textwrap.dedent("""
            from conan import ConanFile
            class BuildReqConan(ConanFile):
                requires = "common/1.0@test/test"
                build_requires = "build_req/1.0@test/test"
        """)
        client.save({"conanfile.py": build_req_req})
        client.run("export . --name=build_req_req --version=1.0 --user=test --channel=test")

        consumer = textwrap.dedent("""
                    [requires]
                    req/1.0@test/test
                    [tool_requires]
                    build_req_req/1.0@test/test
                """)
        client.save({"conanfile.txt": consumer}, clean_first=True)
        client.run("install . --build=missing")
        # This used to assert and trace, now it works
        self.assertIn("conanfile.txt: Applying build-requirement: build_req_req/1.0@test/test",
                      client.out)

    def test_missing_transitive_dependency(self):
        # https://github.com/conan-io/conan/issues/5682
        client = TestClient()
        zlib = textwrap.dedent("""
            from conan import ConanFile
            class ZlibPkg(ConanFile):
                def package_info(self):
                    self.cpp_info.libs = ["myzlib"]
            """)
        client.save({"conanfile.py": zlib})
        client.run("export . --name=zlib --version=1.0 --user=test --channel=test")

        client.save({"conanfile.py": GenConanfile().with_require("zlib/1.0@test/test")})
        client.run("export . --name=freetype --version=1.0 --user=test --channel=test")
        client.save({"conanfile.py": GenConanfile().with_require("freetype/1.0@test/test")})
        client.run("export . --name=fontconfig --version=1.0 --user=test --channel=test")
        harfbuzz = textwrap.dedent("""
            from conan import ConanFile
            class harfbuzz(ConanFile):
                requires = "freetype/1.0@test/test", "fontconfig/1.0@test/test"
                def build(self):
                     self.output.info("ZLIBS LIBS: %s" %self.deps_cpp_info["zlib"].libs)
            """)
        client.save({"conanfile.py": harfbuzz})
        client.run("export . --name=harfbuzz --version=1.0 --user=test --channel=test")

        client.save({"conanfile.py": GenConanfile()
                    .with_tool_requires("fontconfig/1.0@test/test")
                    .with_tool_requires("harfbuzz/1.0@test/test")})
        client.run("install . --build=missing")
        self.assertIn("ZLIBS LIBS: ['myzlib']", client.out)


def test_dependents_new_buildenv():
    client = TestClient()
    boost = textwrap.dedent("""
        from conan import ConanFile
        class Boost(ConanFile):
            def package_info(self):
                self.buildenv_info.define_path("PATH", "myboostpath")
        """)
    other = textwrap.dedent("""
        from conan import ConanFile
        class Other(ConanFile):
            def requirements(self):
                self.requires("boost/1.0")

            def package_info(self):
                self.buildenv_info.append_path("PATH", "myotherpath")
                self.buildenv_info.prepend_path("PATH", "myotherprepend")
        """)
    consumer = textwrap.dedent("""
       from conan import ConanFile
       from conan.tools.env import VirtualBuildEnv
       import os
       class Lib(ConanFile):
           requires = {}
           def generate(self):
               build_env = VirtualBuildEnv(self).vars()
               with build_env.apply():
                   self.output.info("LIB PATH %s" % os.getenv("PATH"))
       """)
    client.save({"boost/conanfile.py": boost,
                 "other/conanfile.py": other,
                 "consumer/conanfile.py": consumer.format('"boost/1.0", "other/1.0"'),
                 "profile_define": "[buildenv]\nPATH=(path)profilepath",
                 "profile_append": "[buildenv]\nPATH+=(path)profilepath",
                 "profile_prepend": "[buildenv]\nPATH=+(path)profilepath"})
    client.run("create boost --name=boost --version=1.0")
    client.run("create other --name=other --version=1.0")
    client.run("install consumer")
    result = os.pathsep.join(["myotherprepend", "myboostpath", "myotherpath"])
    assert "LIB PATH {}".format(result) in client.out

    # Now test if we declare in different order, still topological order should be respected
    client.save({"consumer/conanfile.py": consumer.format('"other/1.0", "boost/1.0"')})
    client.run("install consumer")
    assert "LIB PATH {}".format(result) in client.out

    client.run("install consumer -pr=profile_define")
    assert "LIB PATH profilepath" in client.out
    client.run("install consumer -pr=profile_append")
    result = os.pathsep.join(["myotherprepend", "myboostpath", "myotherpath", "profilepath"])
    assert "LIB PATH {}".format(result) in client.out
    client.run("install consumer -pr=profile_prepend")
    result = os.pathsep.join(["profilepath", "myotherprepend", "myboostpath", "myotherpath"])
    assert "LIB PATH {}".format(result) in client.out


def test_tool_requires_conanfile_txt():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})

    build_req = textwrap.dedent("""
        from conan import ConanFile
        class BuildReqConan(ConanFile):
            pass
        """)

    client.save({"conanfile.py": build_req})
    client.run("export . --name=build_req --version=1.0 --user=test --channel=test")

    consumer = textwrap.dedent("""
                [tool_requires]
                build_req/1.0@test/test
            """)
    client.save({"conanfile.txt": consumer}, clean_first=True)
    client.run("install . --build=missing")
    assert "build_req/1.0@test/test: Created package" in client.out


def test_profile_override_conflict():
    client = TestClient()

    test = textwrap.dedent("""
        from conan import ConanFile
        class Lib(ConanFile):

            def requirements(self):
                self.tool_requires(self.tested_reference_str)

            def test(self):
                pass
        """)
    client.save({"conanfile.py": GenConanfile("protoc"),
                 "test_package/conanfile.py": test,
                 "profile": "[tool_requires]\nprotoc/0.1"})
    client.run("create . --version 0.1 -pr=profile")
    client.run("create . --version 0.2 -pr=profile")
    assert "protoc/0.1: Already installed!" in client.out
    assert "protoc/0.2 (test package)" in client.out
    assert "WARN: The package created was 'protoc/0.1' but the reference being tested " \
           "is 'protoc/0.2'" in client.out


def test_both_context_options_error():
    # https://github.com/conan-io/conan/issues/11385
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "arch"
            options = {"neon": [True, "check", False]}
            default_options = {"neon": True}

            def config_options(self):
                if "arm" not in self.settings.arch:
                    del self.options.neon
            """)
    c.save({"pkg/conanfile.py": pkg,
            "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                   .with_build_requires("pkg/0.1")})
    c.run("export pkg")
    c.run("install consumer -s:b arch=x86_64 -s:h arch=armv8 --build=missing")
    # This failed in Conan 1.X, but now it works
    c.assert_listed_binary({"pkg/0.1": ("a0a41a189feabff576a535d071858191b90beceb", "Build")})
    c.assert_listed_binary({"pkg/0.1": ("62e589af96a19807968167026d906e63ed4de1f5", "Build")},
                           build=True)
    assert "Finalizing install" in c.out


def test_conditional_require_context():
    """ test that we can condition on the context to define a dependency
    """
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
           name = "pkg"
           version = "0.1"
           def requirements(self):
               if self.context == "host":
                   self.requires("dep/1.0")
           """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "consumer/conanfile.py": pkg})
    c.run("create dep")
    c.run("create consumer")
    c.assert_listed_require({"dep/1.0": "Cache"})
    c.run("create consumer --build-require")
    assert "dep/1.0" not in c.out
