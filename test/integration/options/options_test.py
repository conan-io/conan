import textwrap
import unittest


import pytest

from conan.test.utils.tools import TestClient, GenConanfile


class OptionsTest(unittest.TestCase):

    def test_general_scope_options_test_package(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2"]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s" % self.options.shared)
            """)
        test = GenConanfile().with_test("pass")
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o *:shared=1")
        self.assertIn("pkg/0.1@user/testing: BUILD SHARED: 1", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o shared=2")
        assert 'legacy: Unscoped option definition is ambiguous' in client.out
        self.assertIn("pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o *:shared=1")
        self.assertIn("pkg/0.1@user/testing: BUILD SHARED: 1", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o pkg*:shared=2")
        self.assertIn("pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o shared=1")
        self.assertIn("pkg/0.1@user/testing: BUILD SHARED: 1", client.out)

    def test_general_scope_options_test_package_notdefined(self):
        client = TestClient()
        conanfile = GenConanfile()
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o *:shared=True")
        self.assertIn("pkg/0.1@user/testing: Forced build from source", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o shared=False", assert_error=True)
        self.assertIn("option 'shared' doesn't exist", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o *:shared=True")
        self.assertIn("pkg/0.1@user/testing: Forced build from source", client.out)
        self.assertIn("Testing the package: Building", client.out)

    def test_general_scope_priorities(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2", "3"], "other": [4, 5, 6]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s OTHER: %s"
                                     % (self.options.shared, self.options.other))
            """)
        client.save({"conanfile.py": conanfile})
        # Consumer has priority
        client.run("create . --name=pkg --version=0.1 -o *:shared=1 -o shared=2 -o p*:other=4")
        self.assertIn("pkg/0.1: BUILD SHARED: 2 OTHER: 4", client.out)
        # Consumer has priority over pattern, even if the pattern specifies the package name
        client.run("create . --name=pkg --version=0.1 -o *:shared=1 -o pkg/*:shared=2 -o shared=3 -o p*:other=4")
        self.assertIn("pkg/0.1: BUILD SHARED: 3 OTHER: 4", client.out)
        client.run("create . --name=pkg --version=0.1 -o pkg/0.1:shared=2 -o p*:other=4 -o pk*:other=5")
        self.assertIn("pkg/0.1: BUILD SHARED: 2 OTHER: 5", client.out)

        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        # Sorted (longest, alphabetical) patterns, have priority
        client.run("create . --name=pkg --version=0.1 -o *:shared=1 -o pkg/0.1:shared=2 -o other=4")
        self.assertIn("pkg/0.1: BUILD SHARED: 2 OTHER: 4", client.out)
        client.run("create . --name=pkg --version=0.1 -o pk*:shared=2 -o p*:shared=1 -o pkg/0.1:other=5")
        self.assertIn("pkg/0.1: BUILD SHARED: 1 OTHER: 5", client.out)
        client.run("create . --name=pkg --version=0.1 -o pk*:shared=2 -o p*:shared=1 -o pkg/0.1:other=5 -o *g*:other=6")
        self.assertIn("pkg/0.1: BUILD SHARED: 1 OTHER: 6", client.out)

    def test_parsing(self):
        client = TestClient()
        conanfile = '''
from conan import ConanFile
class EqualerrorConan(ConanFile):
    name = "equal"
    version = "1.0.0"
    options = {"opt": ["ANY"]}
    default_options = {"opt": "b=c"}

    def build(self):
        self.output.warning("OPTION %s" % self.options.opt)
'''
        client.save({"conanfile.py": conanfile})
        client.run("export . --user=user --channel=testing")
        conanfile = '''
[requires]
equal/1.0.0@user/testing
[options]
equal/1.0.0@user/testing:opt=a=b
'''
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertIn("OPTION a=b", client.out)

    def test_general_scope_options(self):
        # https://github.com/conan-io/conan/issues/2538
        client = TestClient()
        conanfile_liba = textwrap.dedent("""
            from conan import ConanFile
            class LibA(ConanFile):
                options = {"shared": [True, False]}

                def configure(self):
                    self.output.info("shared=%s" % self.options.shared)
                """)
        client.save({"conanfile.py": conanfile_liba})
        client.run("create . --name=liba --version=0.1 --user=danimtb --channel=testing -o *:shared=True")
        self.assertIn("liba/0.1@danimtb/testing: shared=True", client.out)

        conanfile_libb = textwrap.dedent("""
            from conan import ConanFile
            class LibB(ConanFile):
                options = {"shared": [True, False]}
                requires = "liba/0.1@danimtb/testing"

                def configure(self):
                    self.options["*"].shared = self.options.shared
                    self.output.info("shared=%s" % self.options.shared)
                """)

        for without_configure_line in [True, False]:
            if without_configure_line:
                conanfile = conanfile_libb.replace("self.options[", "#")
            else:
                conanfile = conanfile_libb
            client.save({"conanfile.py": conanfile})

            # Test info
            client.run("graph info . -o *:shared=True")
            self.assertIn("conanfile.py: shared=True", client.out)
            self.assertIn("liba/0.1@danimtb/testing: shared=True", client.out)
            # Test create
            client.run("create . --name=libb --version=0.1 --user=danimtb --channel=testing -o *:shared=True")
            self.assertIn("libb/0.1@danimtb/testing: shared=True", client.out)
            self.assertIn("liba/0.1@danimtb/testing: shared=True", client.out)
            # Test install
            client.run("install . -o *:shared=True")
            self.assertIn("conanfile.py: shared=True", client.out)
            self.assertIn("liba/0.1@danimtb/testing: shared=True", client.out)

    def test_define_nested_option_not_freeze(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                options = {"without_stacktrace": [True, False],
                           "with_stacktrace_backtrace": [True, False]}
                default_options = {"without_stacktrace": True}
                def configure(self):
                    if self.options.without_stacktrace:
                        del self.options.with_stacktrace_backtrace
                    else:
                        self.options.with_stacktrace_backtrace = True

                def build(self):
                    s = self.options.without_stacktrace
                    self.output.info("without_stacktrace: {}".format(s))

                    if "with_stacktrace_backtrace" in self.options:
                        ss = self.options.get_safe("with_stacktrace_backtrace")
                        self.output.info("with_stacktrace_backtrace: {}".format(ss))
                    else:
                        self.output.info("with_stacktrace_backtrace success deleted!")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("create . --name=pkg --version=0.1")
        assert "pkg/0.1: without_stacktrace: True" in c.out
        assert "pkg/0.1: with_stacktrace_backtrace success deleted!" in c.out
        c.run("create . --name=pkg --version=0.1 -o pkg*:without_stacktrace=False")
        assert "pkg/0.1: without_stacktrace: False" in c.out
        assert "pkg/0.1: with_stacktrace_backtrace: True" in c.out

    def test_del_options_configure(self):
        """
        this test was failing because Options was protecting against removal of options with
        already assigned values. This has been relaxed, to make possible this case
        """
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                options = {
                    "shared": [True, False],
                    "fPIC": [True, False],
                }
                default_options = {
                    "shared": False,
                    "fPIC": True,
                }
                def configure(self):
                    if self.options.shared:
                        del self.options.fPIC
            """)
        c.save({"conanfile.py": conanfile})
        c.run("create . --name=pkg --version=0.1")
        c.save({"conanfile.py": GenConanfile("consumer", "1.0").with_requirement("pkg/0.1")},
               clean_first=True)
        c.run("install . -o pkg*:shared=True --build=missing")
        assert "pkg/0.1" in c.out  # Real test is the above doesn't crash

    def test_any(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class EqualerrorConan(ConanFile):
                name = "equal"
                version = "1.0.0"
                options = {"opt": "ANY"}
                default_options = {"opt": "b=c"}

                def generate(self):
                    self.output.warning("OPTION %s" % self.options.opt)
            """)
        c.save({"conanfile.py": conanfile})
        c.run("install .", assert_error=True)
        assert "Error while initializing options. 'b=c' is not a valid 'options.opt' value." in c.out
        assert "Possible values are ['A', 'N', 'Y']" in c.out


class TestOptionsPriorities:
    # https://github.com/conan-io/conan/issues/11571

    @pytest.fixture
    def _client(self):
        lib1 = textwrap.dedent("""
            from conan import ConanFile

            class Lib1Conan(ConanFile):
                name = "lib1"
                version = "1.0"
                options = {"foobar": [True, False]}
                default_options = {"foobar": False}
            """)
        lib2 = textwrap.dedent("""
            from conan import ConanFile

            class Lib2Conan(ConanFile):
                name = "lib2"
                version = "1.0"
                options = {"logic_for_foobar": [True, False]}
                default_options = {"logic_for_foobar": False}

                def requirements(self):
                    self.requires("lib1/1.0")

                def configure(self):
                    self.options["lib1/*"].foobar = self.options.logic_for_foobar
            """)
        c = TestClient()

        c.save({"lib1/conanfile.py": lib1,
                "lib2/conanfile.py": lib2})

        c.run("create lib1 -o lib1/*:foobar=True")
        c.run("create lib1 -o lib1/*:foobar=False")
        c.run("create lib2 -o lib2/*:logic_for_foobar=True")
        c.run("create lib2 -o lib2/*:logic_for_foobar=False")
        return c

    @staticmethod
    def _app(lib1, lib2, configure):
        app = textwrap.dedent("""
           from conan import ConanFile

           class App(ConanFile):

              def requirements(self):
                  self.requires("{}/1.0")
                  self.requires("{}/1.0")

              def {}(self):
                  self.options["lib2/*"].logic_for_foobar = True
                  self.options["lib1/*"].foobar = False

              def generate(self):
                  self.output.info("LIB1 FOOBAR: {{}}".format(
                                                 self.dependencies["lib1"].options.foobar))
                  self.output.info("LIB2 LOGIC: {{}}".format(
                                              self.dependencies["lib2"].options.logic_for_foobar))
           """)
        return app.format(lib1, lib2, configure)

    def test_profile_priority(self, _client):
        c = _client
        c.save({"app/conanfile.py": self._app("lib1", "lib2", "not_configure")})
        # This order works, because lib1 is expanded first, it takes foobar=False
        c.run("install app -o lib2*:logic_for_foobar=True -o lib1*:foobar=False")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: True" in c.out

        # Now swap order
        c.save({"app/conanfile.py": self._app("lib2", "lib1", "not_configure")})
        c.run("install app -o lib2*:logic_for_foobar=True -o lib1*:foobar=False")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: True" in c.out

    def test_lib1_priority(self, _client):
        c = _client
        c.save({"app/conanfile.py": self._app("lib1", "lib2", "not_configure")})
        # This order works, because lib1 is expanded first, it takes foobar=False
        c.run("install app")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: False" in c.out
        c.run("install app -o lib1*:foobar=True")
        assert "conanfile.py: LIB1 FOOBAR: True" in c.out
        assert "conanfile.py: LIB2 LOGIC: False" in c.out
        c.run("install app -o lib2*:logic_for_foobar=True")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: True" in c.out

    def test_lib2_priority(self, _client):
        c = _client
        c.save({"app/conanfile.py": self._app("lib2", "lib1", "not_configure")})
        # This order works, because lib1 is expanded first, it takes foobar=False
        c.run("install app")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: False" in c.out
        c.run("install app -o lib1*:foobar=True")
        assert "conanfile.py: LIB1 FOOBAR: True" in c.out
        assert "conanfile.py: LIB2 LOGIC: False" in c.out
        c.run("install app -o lib2*:logic_for_foobar=True")
        assert "conanfile.py: LIB1 FOOBAR: True" in c.out
        assert "conanfile.py: LIB2 LOGIC: True" in c.out

    def test_consumer_configure_priority(self, _client):
        c = _client
        c.save({"app/conanfile.py": self._app("lib1", "lib2", "configure")})
        c.run("install app")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: True" in c.out

        # Now swap order
        c.save({"app/conanfile.py": self._app("lib1", "lib2", "configure")})
        c.run("install app")
        assert "conanfile.py: LIB1 FOOBAR: False" in c.out
        assert "conanfile.py: LIB2 LOGIC: True" in c.out


def test_configurable_default_options():
    # https://github.com/conan-io/conan/issues/11487
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os"
            options = {"backend": [1, 2, 3]}
            def config_options(self):
                if self.settings.os == "Windows":
                    self.options.backend = 2
                else:
                    self.options.backend = 3
            def package_info(self):
                self.output.info("Package with option:{}!".format(self.options.backend))
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create . -s os=Windows")
    assert "pkg/0.1: Package with option:2!" in c.out
    c.run("create . -s os=Windows -o pkg*:backend=3")
    assert "pkg/0.1: Package with option:3!" in c.out
    c.run("create . -s os=Linux")
    assert "pkg/0.1: Package with option:3!" in c.out
    c.run("create . -s os=Windows -o pkg*:backend=1")
    assert "pkg/0.1: Package with option:1!" in c.out

    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "consumer"
            version = "0.1"
            requires = "pkg/0.1"
            def configure(self):
                self.options["pkg*"].backend = 1
        """)
    c.save({"conanfile.py": consumer})
    c.run("install . -s os=Windows")
    assert "pkg/0.1: Package with option:1!" in c.out
    c.run("create . -s os=Windows")
    assert "pkg/0.1: Package with option:1!" in c.out

    # This fails in Conan 1.X
    c.run("create . -s os=Windows -o pkg*:backend=3")
    assert "pkg/0.1: Package with option:3!" in c.out


class TestMultipleOptionsPatterns:
    """
    https://github.com/conan-io/conan/issues/13240
    """

    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
           version = "1.0"
           options = {"shared": [True, False]}
           default_options = {"shared": False}
           def package_info(self):
               self.output.info(f"SHARED: {self.options.shared}!!")
        """)

    def test_multiple_options_patterns_cli(self):
        """
        https://github.com/conan-io/conan/issues/13240
        """
        c = TestClient()
        consumer = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
              settings = "os", "arch", "compiler", "build_type"

              def requirements(self):
                  self.requires("dep1/1.0")
                  self.requires("dep2/1.0")
                  self.requires("dep3/1.0")
                  self.requires("dep4/1.0")
            """)
        c.save({"dep/conanfile.py": self.dep,
                "pkg/conanfile.py": consumer})
        for d in (1, 2, 3, 4):
            c.run(f"export dep --name dep{d}")

        # match in order left to right
        c.run('install pkg -o *:shared=True -o dep1*:shared=False -o dep2*:shared=False -b missing')
        assert "dep1/1.0: SHARED: False!!" in c.out
        assert "dep2/1.0: SHARED: False!!" in c.out
        assert "dep3/1.0: SHARED: True!!" in c.out
        assert "dep4/1.0: SHARED: True!!" in c.out

        # All match in order, left to right
        c.run('install pkg -o dep1*:shared=False -o dep2*:shared=False -o *:shared=True -b missing')
        assert "dep1/1.0: SHARED: True!!" in c.out
        assert "dep2/1.0: SHARED: True!!" in c.out
        assert "dep3/1.0: SHARED: True!!" in c.out
        assert "dep4/1.0: SHARED: True!!" in c.out

    def test_multiple_options_patterns(self):
        c = TestClient()
        configure_consumer = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os", "arch", "compiler", "build_type"

                def requirements(self):
                    self.requires("dep1/1.0")
                    self.requires("dep2/1.0")
                    self.requires("dep3/1.0")
                    self.requires("dep4/1.0")

                def configure(self):
                    self.options["*"].shared = True
                    # Without * also works, equivalent to dep1/*
                    self.options["dep1"].shared = False
                    self.options["dep2*"].shared = False
            """)
        c.save({"dep/conanfile.py": self.dep,
                "pkg/conanfile.py": configure_consumer})
        for d in (1, 2, 3, 4):
            c.run(f"export dep --name dep{d}")

        c.run("install pkg --build=missing")
        assert "dep1/1.0: SHARED: False!!" in c.out
        assert "dep2/1.0: SHARED: False!!" in c.out
        assert "dep3/1.0: SHARED: True!!" in c.out
        assert "dep4/1.0: SHARED: True!!" in c.out

    def test_multiple_options_patterns_order(self):
        c = TestClient()
        configure_consumer = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os", "arch", "compiler", "build_type"

                def requirements(self):
                    self.requires("dep1/1.0")
                    self.requires("dep2/1.0")
                    self.requires("dep3/1.0")
                    self.requires("dep4/1.0")

                def configure(self):
                    self.options["dep1*"].shared = False
                    self.options["dep2*"].shared = False
                    self.options["*"].shared = True
            """)
        c.save({"dep/conanfile.py": self.dep,
                "pkg/conanfile.py": configure_consumer})
        for d in (1, 2, 3, 4):
            c.run(f"export dep --name dep{d}")

        c.run("install pkg --build=missing")
        assert "dep1/1.0: SHARED: True!!" in c.out
        assert "dep2/1.0: SHARED: True!!" in c.out
        assert "dep3/1.0: SHARED: True!!" in c.out
        assert "dep4/1.0: SHARED: True!!" in c.out


class TestTransitiveOptionsShared:
    """
    https://github.com/conan-io/conan/issues/13854
    """
    @pytest.fixture()
    def client(self):
        c = TestClient()
        c.save({"toollib/conanfile.py": GenConanfile("toollib", "0.1").with_shared_option(False),
                "tool/conanfile.py": GenConanfile("tool", "0.1").with_shared_option(False)
                                                                .with_requires("toollib/0.1"),
                "dep2/conanfile.py": GenConanfile("dep2", "0.1").with_shared_option(False)
                                                                .with_tool_requires("tool/0.1"),
                "dep1/conanfile.py": GenConanfile("dep1", "0.1").with_shared_option(False)
                                                                .with_requires("dep2/0.1"),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_shared_option(False)
                                                              .with_requires("dep1/0.1"),
                "app/conanfile.txt": "[requires]\npkg/0.1"})
        c.run("export toollib")
        c.run("export tool")
        c.run("export dep2")
        c.run("export dep1")
        c.run("export pkg")
        return c

    @staticmethod
    def check(client):
        # tools and libs in build context do not get propagated the options
        for dep in ("toollib", "tool"):
            client.run(f"list {dep}/*:*")
            assert "shared: False" in client.out
        # But the whole host context does
        for dep in ("dep1", "dep2", "pkg"):
            client.run(f"list {dep}/*:*")
            assert "shared: True" in client.out

    def test_transitive_options_shared_cli(self, client):
        client.run("install app --build=missing -o *:shared=True")
        self.check(client)

    def test_transitive_options_shared_profile(self, client):
        client.save({"profile": "[options]\n*:shared=True"})
        client.run("install app --build=missing -pr=profile")
        self.check(client)

    def test_transitive_options_conanfile_txt(self, client):
        client.save({"app/conanfile.txt": "[requires]\npkg/0.1\n[options]\n*:shared=True\n"})
        client.run("install app --build=missing")
        self.check(client)

    def test_transitive_options_conanfile_py(self, client):
        client.save({"app/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                       .with_default_option("*:shared", True)})
        client.run("install app/conanfile.py --build=missing")
        self.check(client)

    def test_transitive_options_conanfile_py_create(self, client):
        conanfile = GenConanfile("app", "0.1").with_requires("pkg/0.1") \
                                              .with_default_option("*:shared", True)
        client.save({"app/conanfile.py": conanfile})
        client.run("create app --build=missing")
        self.check(client)


def test_options_no_user_channel_patterns():
    c = TestClient()
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg(ConanFile):
            options = {"myoption": [1, 2, 3]}
            def configure(self):
                self.output.info(f"MYOPTION: {self.options.myoption}")
            """)
    c.save({"dep/conanfile.py": conanfile,
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep1/0.1", "dep2/0.1@user",
                                                                         "dep3/0.1@user/channel")})
    c.run("export dep --name=dep1 --version=0.1")
    c.run("export dep --name=dep2 --version=0.1 --user=user")
    c.run("export dep --name=dep3 --version=0.1 --user=user --channel=channel")

    c.run("graph info pkg -o *:myoption=3 -o *@:myoption=1")
    assert "dep1/0.1: MYOPTION: 1" in c.out
    assert "dep2/0.1@user: MYOPTION: 3" in c.out
    assert "dep3/0.1@user/channel: MYOPTION: 3" in c.out

    # Recall that order is also important latest matching pattern wins
    c.run("graph info pkg -o *@:myoption=1 -o *:myoption=1")
    assert "dep1/0.1: MYOPTION: 1" in c.out
    assert "dep2/0.1@user: MYOPTION: 1" in c.out
    assert "dep3/0.1@user/channel: MYOPTION: 1" in c.out

    # This is a bit weird negation approach, but it works = all packages that have user channel
    c.run("graph info pkg -o *:myoption=3 -o ~*@:myoption=1")
    assert "dep1/0.1: MYOPTION: 3" in c.out
    assert "dep2/0.1@user: MYOPTION: 1" in c.out
    assert "dep3/0.1@user/channel: MYOPTION: 1" in c.out

    # Which is identical to '~*@' == '*@*'
    c.run("graph info pkg -o *:myoption=3 -o *@*:myoption=1")
    assert "dep1/0.1: MYOPTION: 3" in c.out
    assert "dep2/0.1@user: MYOPTION: 1" in c.out
    assert "dep3/0.1@user/channel: MYOPTION: 1" in c.out


class TestTransitiveOptionsSharedInvisible:
    """
    https://github.com/conan-io/conan/issues/13854
    When a requirement is visible=False
    """
    @pytest.fixture()
    def client(self):
        c = TestClient()
        c.save({"dep2/conanfile.py": GenConanfile("dep2", "0.1").with_shared_option(False),
                "dep1/conanfile.py": GenConanfile("dep1", "0.1").with_shared_option(False)
                                                                .with_requirement("dep2/0.1",
                                                                                  visible=False),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_shared_option(False)
                                                              .with_requires("dep1/0.1"),
                "app/conanfile.txt": "[requires]\npkg/0.1"})
        c.run("export dep2")
        c.run("export dep1")
        c.run("export pkg")
        return c

    @staticmethod
    def check(client, value):
        for dep in ("dep1", "pkg"):
            client.run(f"list {dep}/*:*")
            assert f"shared: True" in client.out

        # dep2 cannot be affected from downstream conanfile consumers options, only from profile
        client.run(f"list dep2/*:*")
        assert f"shared: {value}" in client.out

    def test_transitive_options_shared_cli(self, client):
        client.run("install app --build=missing -o *:shared=True")
        self.check(client, True)

    def test_transitive_options_shared_profile(self, client):
        client.save({"profile": "[options]\n*:shared=True"})
        client.run("install app --build=missing -pr=profile")
        self.check(client, True)

    def test_transitive_options_conanfile_txt(self, client):
        client.save({"app/conanfile.txt": "[requires]\npkg/0.1\n[options]\n*:shared=True\n"})
        client.run("install app --build=missing")
        self.check(client, False)

    def test_transitive_options_conanfile_py(self, client):
        client.save({"app/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                       .with_default_option("*:shared", True)})
        client.run("install app/conanfile.py --build=missing")
        self.check(client, False)

    def test_transitive_options_conanfile_py_create(self, client):
        conanfile = GenConanfile("app", "0.1").with_requires("pkg/0.1") \
                                              .with_default_option("*:shared", True)
        client.save({"app/conanfile.py": conanfile})
        client.run("create app --build=missing")
        self.check(client, False)


class TestImportantOptions:
    @pytest.mark.parametrize("pkg", ["liba", "libb", "app"])
    def test_important_options(self, pkg):
        c = TestClient()

        liba = GenConanfile("liba", "0.1").with_option("myoption", [1, 2, 3])
        libb = GenConanfile("libb", "0.1").with_requires("liba/0.1")
        app = GenConanfile().with_requires("libb/0.1")
        if pkg == "liba":
            liba.with_default_option("myoption!", 2)
        elif pkg == "libb":
            libb.with_default_option("*:myoption!", 2)
        elif pkg == "app":
            app.with_default_option("*:myoption!", 2)
        package_id = textwrap.dedent("""
            def package_id(self):
                self.output.info(f"MYOPTION: {self.info.options.myoption}")
            """)
        liba = str(liba) + textwrap.indent(package_id, "    ")

        c.save({"liba/conanfile.py": liba,
                "libb/conanfile.py": libb,
                "app/conanfile.py": app})
        c.run("export liba")
        c.run("export libb")

        c.run("graph info app -o *:myoption=3")
        assert "liba/0.1: MYOPTION: 2" in c.out

        # And the profile can always important-override the option
        c.run("graph info app -o *:myoption!=3")
        assert "liba/0.1: MYOPTION: 3" in c.out

    def test_profile_shows_important(self):
        c = TestClient()
        c.run("profile show  -o *:myoption!=3")
        assert "*:myoption!=3" in c.out

    def test_important_options_recipe_priority(self):
        c = TestClient()

        liba = GenConanfile("liba", "0.1").with_option("myoption", [1, 2, 3, 4])\
                                          .with_default_option("myoption!", 1)
        libb = GenConanfile("libb", "0.1").with_requires("liba/0.1")\
                                          .with_default_option("*:myoption!", 2)
        app = GenConanfile().with_requires("libb/0.1").with_default_option("*:myoption!", 3)

        package_id = textwrap.dedent("""
            def package_id(self):
                self.output.info(f"MYOPTION: {self.info.options.myoption}")
            """)
        liba = str(liba) + textwrap.indent(package_id, "    ")

        c.save({"liba/conanfile.py": liba,
                "libb/conanfile.py": libb,
                "app/conanfile.py": app})
        c.run("export liba")
        c.run("export libb")

        c.run("graph info app")
        assert "liba/0.1: MYOPTION: 3" in c.out

        c.run("graph info app -o *:myoption!=4")
        assert "liba/0.1: MYOPTION: 4" in c.out

    def test_wrong_option_syntax_no_trace(self):
        tc = TestClient(light=True)
        tc.save({"conanfile.py": GenConanfile().with_option("myoption", [1, 2, 3])})
        tc.run('create . -o="&:myoption"', assert_error=True)
        assert "ValueError" not in tc.out
        assert "Error while parsing option" in tc.out


class TestConflictOptionsWarnings:

    def test_options_warnings(self):
        c = TestClient()
        liba = GenConanfile("liba", "0.1").with_option("myoption", [1, 2, 3], default=1)
        libb = GenConanfile("libb", "0.1").with_requires("liba/0.1")
        libc = GenConanfile("libc", "0.1").with_requirement("liba/0.1", options={"myoption": 2})
        app = GenConanfile().with_requires("libb/0.1", "libc/0.1")

        c.save({"liba/conanfile.py": liba,
                "libb/conanfile.py": libb,
                "libc/conanfile.py": libc,
                "app/conanfile.py": app})
        c.run("export liba")
        c.run("export libb")
        c.run("export libc")

        c.run("graph info app")
        expected = textwrap.dedent("""\
            Options conflicts
                liba/0.1:myoption=1 (current value)
                    libc/0.1->myoption=2
                It is recommended to define options values in profiles, not in recipes
            """)
        assert expected in c.out
