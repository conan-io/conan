import os
import textwrap
import time
import unittest

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient, GenConanfile


class PyRequiresExtendTest(unittest.TestCase):

    @staticmethod
    def _define_base(client):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                def source(self):
                    self.output.info("My cool source!")
                def build(self):
                    self.output.info("My cool build!")
                def package(self):
                    self.output.info("My cool package!")
                def package_info(self):
                    self.output.info("My cool package_info!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")

    def test_reuse(self):
        client = TestClient(light=True, default_server_user=True)
        self._define_base(client)
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)

        client.run("upload * --confirm -r default")
        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)
        client.run("remove * -c")
        client.run("download pkg/0.1@user/testing#latest:* -r default")
        self.assertIn(f"pkg/0.1@user/testing: Package installed {package_id}", client.out)
        # But it's broken with a single download
        client.run("install --requires=pkg/0.1@user/testing -nr", assert_error=True)
        assert "Cannot resolve python_requires 'base/1.1@user/testing'" in client.out
        # If pyrequires are expected, then first graph info -f=json and then get recipes from pkglist
        client.run("remove * -c")
        client.run("graph info --requires=pkg/0.1@user/testing -f=json", redirect_stdout="graph_info.json")
        # We can even remove from the cache now (The pyrequires is already downloaded in the above step)
        client.run("remove * -c")
        client.run("list --graph=graph_info.json --graph-recipes=* -f=json", redirect_stdout="pkglist.json")
        client.run("download --list=pkglist.json -r default")
        assert "Downloading recipe 'base/1.1@user/testing" in client.out
        client.run("install --requires=pkg/0.1@user/testing -nr")
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)

    def test_reuse_super(self):
        client = TestClient(light=True, default_server_user=True)
        self._define_base(client)
        reuse = textwrap.dedent("""
               from conan import ConanFile
               class PkgTest(ConanFile):
                   python_requires = "base/1.1@user/testing"
                   python_requires_extend = "base.MyConanfileBase"

                   def source(self):
                       super().source()
                       self.output.info("MY OWN SOURCE")
               """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("source . --name=pkg --version=0.1")
        assert "conanfile.py (pkg/0.1): My cool source!" in client.out
        assert "conanfile.py (pkg/0.1): MY OWN SOURCE" in client.out

    def test_reuse_dot(self):
        client = TestClient(light=True, default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                def build(self):
                    self.output.info("My cool build!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=my.base --version=1.1 --user=user --channel=testing")
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "my.base/1.1@user/testing"
                python_requires_extend = "my.base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: My cool build!", client.out)

    def test_with_alias(self):
        client = TestClient(light=True)
        self._define_base(client)
        client.alias("base/latest@user/testing", "base/1.1@user/testing")

        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                name = "pkg"
                version = "1.0"
                python_requires = "base/latest@user/testing"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("install .", assert_error=True)
        assert "python-requires 'alias' are not supported in Conan 2.0" in client.out
        client.run("create .", assert_error=True)
        assert "python-requires 'alias' are not supported in Conan 2.0" in client.out

    def test_reuse_version_ranges(self):
        client = TestClient(light=True)
        self._define_base(client)

        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/[>1.0 <1.2]@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        client.assert_listed_require({"base/1.1@user/testing": "Cache"}, python=True)
        self.assertIn("pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)

    def test_multiple_reuse(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class SourceBuild(ConanFile):
                def source(self):
                    self.output.info("My cool source!")
                def build(self):
                    self.output.info("My cool build!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=sourcebuild --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class PackageInfo(ConanFile):
                def package(self):
                    self.output.info("My cool package!")
                def package_info(self):
                    self.output.info("My cool package_info!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=packageinfo --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "sourcebuild/1.0@user/channel", "packageinfo/1.0@user/channel"
                python_requires_extend = "sourcebuild.SourceBuild", "packageinfo.PackageInfo"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)

    @staticmethod
    def test_transitive_access():
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=base --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Helper(ConanFile):
                python_requires = "base/1.0@user/channel"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=helper --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                python_requires = "helper/1.0@user/channel"
                def build(self):
                    self.python_requires["base"]
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=channel")
        assert "pkg/0.1@user/channel: Created package" in client.out

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                python_requires = "helper/1.0@user/channel"
                python_requires_extend = "base.HelloConan"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=channel")
        assert "pkg/0.1@user/channel: Created package" in client.out

    def test_multiple_requires_error(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            myvar = 123
            def myfunct():
                return 123
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg1 --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            myvar = 234
            def myfunct():
                return 234
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg2 --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "pkg1/1.0@user/channel", "pkg2/1.0@user/channel"
                def build(self):
                    self.output.info("PKG1 N: %s" % self.python_requires["pkg1"].conanfile.name)\
                               .info("PKG1 V: %s" % self.python_requires["pkg1"].conanfile.version)\
                               .info("PKG1 U: %s" % self.python_requires["pkg1"].conanfile.user)\
                               .info("PKG1 C: %s" % self.python_requires["pkg1"].conanfile.channel)\
                               .info("PKG1 : %s" % self.python_requires["pkg1"].module.myvar)\
                               .info("PKG2 : %s" % self.python_requires["pkg2"].module.myvar)\
                               .info("PKG1F : %s" % self.python_requires["pkg1"].module.myfunct())\
                               .info("PKG2F : %s" % self.python_requires["pkg2"].module.myfunct())
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=testing")
        self.assertIn("consumer/0.1@user/testing: PKG1 N: pkg1", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG1 V: 1.0", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG1 U: user", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG1 C: channel", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG1 : 123", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG2 : 234", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG1F : 123", client.out)
        self.assertIn("consumer/0.1@user/testing: PKG2F : 234", client.out)

    def test_local_import(self):
        client = TestClient(light=True, default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            import mydata
            class MyConanfileBase(ConanFile):
                exports = "*.py"
                def source(self):
                    self.output.info(mydata.src)
                def build(self):
                    self.output.info(mydata.build)
                def package(self):
                    self.output.info(mydata.pkg)
                def package_info(self):
                    self.output.info(mydata.info)
            """)
        mydata = textwrap.dedent("""
            src = "My cool source!"
            build = "My cool build!"
            pkg = "My cool package!"
            info = "My cool package_info!"
            """)
        client.save({"conanfile.py": conanfile,
                     "mydata.py": mydata})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)

        client.run("upload * --confirm -r default")
        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)
        client.run("remove * -c")
        client.run("download pkg/0.1@user/testing#*:* -r default")
        self.assertIn(f"pkg/0.1@user/testing: Package installed {package_id}", client.out)

    def test_reuse_class_members(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                license = "MyLicense"
                author = "author@company.com"
                exports = "*.txt"
                exports_sources = "*.h"
                short_paths = True
                generators = "CMakeToolchain"
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "some content"})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")

        reuse = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            import os
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def build(self):
                    self.output.info("Exports sources! %s" % self.exports_sources)
                    self.output.info("HEADER CONTENT!: %s" % load(self, "header.h"))
                    self.output.info("Short paths! %s" % self.short_paths)
                    self.output.info("License! %s" % self.license)
                    self.output.info("Author! %s" % self.author)
                    assert os.path.exists("conan_toolchain.cmake")
            """)
        client.save({"conanfile.py": reuse,
                     "header.h": "pkg new header contents",
                     "other.txt": "text"})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: Exports sources! *.h", client.out)
        self.assertIn("pkg/0.1@user/testing: Copied 1 '.txt' file: other.txt", client.out)
        self.assertIn("pkg/0.1@user/testing: Copied 1 '.h' file: header.h", client.out)
        self.assertIn("pkg/0.1@user/testing: Short paths! True", client.out)
        self.assertIn("pkg/0.1@user/testing: License! MyLicense", client.out)
        self.assertIn("pkg/0.1@user/testing: Author! author@company.com", client.out)
        self.assertIn("pkg/0.1@user/testing: HEADER CONTENT!: pkg new header contents", client.out)
        ref = RecipeReference.loads("pkg/0.1@user/testing")
        self.assertTrue(os.path.exists(os.path.join(client.get_latest_ref_layout(ref).export(),
                                                    "other.txt")))

    def test_reuse_system_requirements(self):
        # https://github.com/conan-io/conan/issues/7718
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           class MyConanfileBase(ConanFile):
               def system_requirements(self):
                   self.output.info("My system_requirements %s being called!" % self.name)
           """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: My system_requirements pkg being called!", client.out)

    def test_reuse_requirements(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
                   from conan import ConanFile
                   class MyConanfileBase(ConanFile):
                       def requirements(self):
                           self.output.info("My requirements %s being called!" % self.name)
                           self.requires("foo/1.0")
                   """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")
        client.save({"conanfile.py": GenConanfile("foo", "1.0")})
        client.run("create .")
        reuse = textwrap.dedent("""
                    from conan import ConanFile
                    class PkgTest(ConanFile):
                        python_requires = "base/1.1@user/testing"
                        python_requires_extend = "base.MyConanfileBase"
                    """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: My requirements pkg being called!", client.out)
        client.assert_listed_require({"foo/1.0#f5288356d9cc303f25cb05bccbad8fbb": "Cache"})

    def test_overwrite_class_members(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                license = "MyLicense"
                author = "author@company.com"
                settings = "os", # tuple!
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")

        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                license = "MIT"
                author = "frodo"
                settings = "arch", # tuple!
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"

                def init(self):
                    base = self.python_requires["base"].module.MyConanfileBase
                    self.settings = base.settings + self.settings
                    self.license = base.license

                def build(self):
                    self.output.info("License! %s" % self.license)
                    self.output.info("Author! %s" % self.author)
                    self.output.info("os: %s arch: %s" % (self.settings.get_safe("os"),
                                                          self.settings.arch))
            """)
        client.save({"conanfile.py": reuse})
        client.run(
            "create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Windows -s arch=armv7")
        self.assertIn("pkg/0.1@user/testing: License! MyLicense", client.out)
        self.assertIn("pkg/0.1@user/testing: Author! frodo", client.out)
        self.assertIn("pkg/0.1@user/testing: os: Windows arch: armv7", client.out)

    def test_failure_init_method(self):
        client = TestClient()
        base = textwrap.dedent("""
            from conan import ConanFile
            class MyBase(object):
                settings = "os", "build_type", "arch"
                options = {"base_option": [True, False]}
                default_options = {"base_option": False}

            class BaseConanFile(ConanFile):
                pass
            """)
        client.save({"conanfile.py": base})
        client.run("export . --name=base --version=1.0")
        derived = textwrap.dedent("""
            from conan import ConanFile
            class DerivedConan(ConanFile):
                settings = "os", "build_type", "arch"

                python_requires = "base/1.0"
                python_requires_extend = 'base.MyBase'

                options = {"derived_option": [True, False]}
                default_options = {"derived_option": False}

                def init(self):
                    base = self.python_requires['base'].module.MyBase
                    self.options.update(base.options, base.default_options)
                """)
        client.save({"conanfile.py": derived})
        client.run("create . --name=pkg --version=0.1 -o base_option=True -o derived_option=True")
        self.assertIn("pkg/0.1: Created package", client.out)
        client.run("create . --name=pkg --version=0.1 -o whatever=True", assert_error=True)
        assert "Possible options are ['derived_option', 'base_option']" in client.out

    def test_transitive_imports_conflicts(self):
        # https://github.com/conan-io/conan/issues/3874
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            import myhelper
            class SourceBuild(ConanFile):
                exports = "*.py"
            """)
        helper = textwrap.dedent("""
            def myhelp(output):
                output.info("MyHelperOutput!")
            """)
        client.save({"conanfile.py": conanfile,
                     "myhelper.py": helper})
        client.run("export . --name=base1 --version=1.0 --user=user --channel=channel")
        client.save({"myhelper.py": helper.replace("MyHelperOutput!", "MyOtherHelperOutput!")})
        client.run("export . --name=base2 --version=1.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class MyConanfileBase(ConanFile):
                python_requires = "base2/1.0@user/channel", "base1/1.0@user/channel"
                def build(self):
                    self.python_requires["base1"].module.myhelper.myhelp(self.output)
                    self.python_requires["base2"].module.myhelper.myhelp(self.output)
            """)
        # This should work, even if there is a local "myhelper.py" file, which could be
        # accidentaly imported (and it was, it was a bug)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: MyHelperOutput!", client.out)
        self.assertIn("pkg/0.1@user/testing: MyOtherHelperOutput!", client.out)

        # Now, the same, but with "clean_first=True", should keep working
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: MyHelperOutput!", client.out)
        self.assertIn("pkg/0.1@user/testing: MyOtherHelperOutput!", client.out)

    def test_update(self):
        client = TestClient(light=True, default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            somevar = 42
            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")

        client2 = TestClient(light=True, servers=client.servers, inputs=["user", "password"])
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def configure(self):
                    self.output.info("PYTHON REQUIRE VAR %s"
                                     % self.python_requires["base"].module.somevar)
        """)

        client2.save({"conanfile.py": reuse})
        client2.run("install .")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 42", client2.out)

        client.save({"conanfile.py": conanfile.replace("42", "143")})
        time.sleep(1)  # guarantee time offset
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")

        client2.run("install . --update")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 143", client2.out)

    def test_update_ranges(self):
        # Same as the above, but using a version range, and no --update
        # https://github.com/conan-io/conan/issues/4650#issuecomment-497464305
        client = TestClient(light=True, default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            somevar = 42
            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")

        client2 = TestClient(light=True, servers=client.servers, inputs=["user", "password"])
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/[>1.0]@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def configure(self):
                    self.output.info("PYTHON REQUIRE VAR %s"
                                     % self.python_requires["base"].module.somevar)
        """)

        client2.save({"conanfile.py": reuse})
        client2.run("install .")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 42", client2.out)

        client.save({"conanfile.py": conanfile.replace("42", "143")})
        # Make sure to bump the version!
        client.run("export . --name=base --version=1.2 --user=user --channel=testing")
        client.run("upload * --confirm -r default")

        client2.run("install . --update")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 143", client2.out)

    def test_duplicate_pyreq(self):
        t = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class PyReq(ConanFile):
                pass
        """)
        t.save({"conanfile.py": conanfile})
        t.run("export . --name=pyreq --version=1.0 --user=user --channel=channel")
        t.run("export . --name=pyreq --version=2.0 --user=user --channel=channel")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                python_requires = "pyreq/1.0@user/channel", "pyreq/2.0@user/channel"
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . --name=name --version=version --user=user --channel=channel",
              assert_error=True)
        self.assertIn("ERROR: Error loading conanfile", t.out)
        self.assertIn("The python_require 'pyreq' already exists", t.out)

    def test_local_build(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": "var=42\n" + str(GenConanfile())})
        client.run("export . --name=tool --version=0.1 --user=user --channel=channel")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                def source(self):
                    self.output.info("Pkg1 source: %s" % self.python_requires["tool"].module.var)
                def build(self):
                    self.output.info("Pkg1 build: %s" % self.python_requires["tool"].module.var)
                def package(self):
                    self.output.info("Pkg1 package: %s" % self.python_requires["tool"].module.var)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn("conanfile.py: Pkg1 source: 42", client.out)
        client.run("install .")
        client.run("build .")
        self.assertIn("conanfile.py: Pkg1 build: 42", client.out)
        client.run("export-pkg . --name=pkg1 --version=0.1 --user=user --channel=testing")

    def test_reuse_name_version(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            import os

            class Source(object):
                def set_name(self):
                    self.name = load(self, "name.txt")

                def set_version(self):
                    self.version = load(self, "version.txt")

            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=tool --version=0.1 --user=user --channel=channel")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                python_requires_extend = "tool.Source"
                def source(self):
                    self.output.info("Pkg1 source: %s:%s" % (self.name, self.version))
                def build(self):
                    self.output.info("Pkg1 build: %s:%s" % (self.name, self.version))
                def package(self):
                    self.output.info("Pkg1 package: %s:%s" % (self.name, self.version))
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "mypkg",
                     "version.txt": "myversion"})
        client.run("export .")
        self.assertIn("mypkg/myversion: Exported", client.out)
        client.run("create .")
        self.assertIn("mypkg/myversion: Pkg1 source: mypkg:myversion", client.out)
        self.assertIn("mypkg/myversion: Pkg1 build: mypkg:myversion", client.out)
        self.assertIn("mypkg/myversion: Pkg1 package: mypkg:myversion", client.out)

    def test_reuse_export_sources(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                exports = "*"
            """)
        client.save({"conanfile.py": conanfile,
                     "file.h": "myheader",
                     "folder/other.h": "otherheader"})
        client.run("export . --name=tool --version=0.1 --user=user --channel=channel")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            import os
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                def source(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Source: tool header: %s" % load(self, file_h))
                    self.output.info("Source: tool other: %s" % load(self, other_h))
                def build(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Build: tool header: %s" % load(self, file_h))
                    self.output.info("Build: tool other: %s" % load(self, other_h))
                def package(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Package: tool header: %s" % load(self, file_h))
                    self.output.info("Package: tool other: %s" % load(self, other_h))
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "MyPkg",
                     "version.txt": "MyVersion"})
        client.run("export . --name=pkg --version=1.0 --user=user --channel=channel")
        self.assertIn("pkg/1.0@user/channel: Exported", client.out)
        client.run("create . --name=pkg --version=1.0 --user=user --channel=channel")
        self.assertIn("pkg/1.0@user/channel: Source: tool header: myheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Source: tool other: otherheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Build: tool header: myheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Build: tool other: otherheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Package: tool header: myheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Package: tool other: otherheader", client.out)

        # The local flow
        client.run("install .")
        client.run("source .")
        self.assertIn("conanfile.py: Source: tool header: myheader", client.out)
        self.assertIn("conanfile.py: Source: tool other: otherheader", client.out)
        client.run("build .")
        self.assertIn("conanfile.py: Build: tool header: myheader", client.out)
        self.assertIn("conanfile.py: Build: tool other: otherheader", client.out)

    def test_reuse_editable_exports(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MyConanfileBase(ConanFile):
                exports = "*"
            """)
        client.save({"conanfile.py": conanfile,
                     "file.h": "myheader",
                     "folder/other.h": "otherheader"})
        client.run("editable add . --name=tool --version=0.1")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            import os
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1"
                def source(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Source: tool header: %s" % load(self, file_h))
                    self.output.info("Source: tool other: %s" % load(self, other_h))
                def build(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Build: tool header: %s" % load(self, file_h))
                    self.output.info("Build: tool other: %s" % load(self, other_h))
            """)

        client2 = TestClient(light=True, cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile,
                      "name.txt": "MyPkg",
                      "version.txt": "MyVersion"})

        # The local flow
        client2.run("install .")
        client2.run("source .")
        self.assertIn("conanfile.py: Source: tool header: myheader", client2.out)
        self.assertIn("conanfile.py: Source: tool other: otherheader", client2.out)
        client2.run("build .")
        self.assertIn("conanfile.py: Build: tool header: myheader", client2.out)
        self.assertIn("conanfile.py: Build: tool other: otherheader", client2.out)

    def test_build_id(self):
        client = TestClient(light=True, default_server_user=True)
        self._define_base(client)
        reuse = textwrap.dedent("""
            from conan import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def build_id(self):
                    pass
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("pkg/0.1@user/testing: My cool package_info!", client.out)

    def test_options_errors(self):
        c = TestClient(light=True)
        base = textwrap.dedent("""
            from conan import ConanFile
            class BaseConan:
                options = {"base": [True, False]}
                default_options = {"base": True}

            class PyReq(ConanFile):
                name = "base"
                version = "1.0.0"
                package_type = "python-require"
                """)
        derived = textwrap.dedent("""
            import conan

            class DerivedConan(conan.ConanFile):
                name = "derived"
                python_requires = "base/1.0.0"
                python_requires_extend = "base.BaseConan"
                options = {"derived": [True, False]}
                default_options = {"derived": False}

                def init(self):
                    base = self.python_requires["base"].module.BaseConan
                    self.options.update(base.options, base.default_options)

                def generate(self):
                    self.output.info(f"OptionBASE: {self.options.base}")
                    self.output.info(f"OptionDERIVED: {self.options.derived}")
            """)
        c.save({"base/conanfile.py": base,
                "derived/conanfile.py": derived})
        c.run("create base")
        c.run("install derived")
        assert "OptionBASE: True" in c.out
        assert "OptionDERIVED: False" in c.out


def test_transitive_python_requires():
    # https://github.com/conan-io/conan/issues/8546
    client = TestClient(light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        myvar = 123
        def myfunct():
            return 234
        class SharedFunction(ConanFile):
            name = "shared-function"
            version = "1.0"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=user --channel=channel")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class BaseClass(ConanFile):
            name = "base-class"
            version = "1.0"
            python_requires = "shared-function/1.0@user/channel"
            def build(self):
                pyreqs = self.python_requires
                v = pyreqs["shared-function"].module.myvar  # v will be 123
                f = pyreqs["shared-function"].module.myfunct()  # f will be 234
                self.output.info("%s, %s" % (v, f))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=user --channel=channel")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            python_requires = "base-class/1.0@user/channel"
            python_requires_extend = "base-class.BaseClass"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --user=user --channel=channel")
    assert "consumer/1.0@user/channel: Calling build()\nconsumer/1.0@user/channel: 123, 234" in \
           client.out


def test_transitive_diamond_python_requires():
    client = TestClient(light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        myvar = 123
        def myfunct():
            return 234
        class SharedFunction(ConanFile):
            name = "shared-function"
            version = "1.0"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=user --channel=channel")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        myvar = 222
        def myfunct():
            return 2222
        class SharedFunction2(ConanFile):
            name = "shared-function2"
            version = "1.0"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=user --channel=channel")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class BaseClass(ConanFile):
            name = "base-class"
            version = "1.0"
            python_requires = "shared-function/1.0@user/channel", "shared-function2/1.0@user/channel"
            def build(self):
                pyreqs = self.python_requires
                v = pyreqs["shared-function"].module.myvar  # v will be 123
                f = pyreqs["shared-function2"].module.myfunct()  # f will be 2222
                self.output.info("%s, %s" % (v, f))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=user --channel=channel")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class BaseClass2(ConanFile):
            name = "base-class2"
            version = "1.0"
            python_requires = "shared-function/1.0@user/channel", "shared-function2/1.0@user/channel"
            def package(self):
                pyreqs = self.python_requires
                v = pyreqs["shared-function2"].module.myvar  # v will be 222
                f = pyreqs["shared-function"].module.myfunct()  # f will be 234
                self.output.info("%s, %s" % (v, f))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=user --channel=channel")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            python_requires = "base-class/1.0@user/channel", "base-class2/1.0@user/channel"
            python_requires_extend = "base-class.BaseClass", "base-class2.BaseClass2"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --user=user --channel=channel")
    assert "consumer/1.0@user/channel: Calling build()\nconsumer/1.0@user/channel: 123, 2222" in \
           client.out
    assert "consumer/1.0@user/channel: Calling package()\nconsumer/1.0@user/channel: 222, 234" in \
           client.out


class TestConflictPyRequires:
    # https://github.com/conan-io/conan/issues/15016
    def test_diamond_conflict_fixed(self):
        c = TestClient(light=True)

        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "sub1/conanfile.py": GenConanfile("sub1", "1.0").with_python_requires("tool/1.0"),
                "sub2/conanfile.py": GenConanfile("sub2", "1.0").with_python_requires("tool/1.1"),
                "app/conanfile.py": GenConanfile().with_python_requires("sub1/1.0", "sub2/1.0")})
        c.run("export tool --version=1.0")
        c.run("export tool --version=1.1")
        c.run("export sub1")
        c.run("export sub2")
        c.run("install app", assert_error=True)
        assert "Conflict in py_requires tool/1.0 - tool/1.1" in c.out

    def test_diamond_conflict_ranges(self):
        c = TestClient(light=True)

        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "sub1/conanfile.py": GenConanfile("sub1", "1.0").with_python_requires("tool/[*]"),
                "sub2/conanfile.py": GenConanfile("sub2", "1.0").with_python_requires("tool/1.0"),
                "app/conanfile.py": GenConanfile().with_python_requires("sub1/1.0", "sub2/1.0")})
        c.run("export tool --version=1.0")
        c.run("export tool --version=1.1")
        c.run("export sub1")
        c.run("export sub2")
        c.run("install app", assert_error=True)
        assert "Conflict in py_requires tool/1.1 - tool/1.0" in c.out


def test_multiple_reuse():
    """ test how to enable the multiple code reuse for custom user generators
        # https://github.com/conan-io/conan/issues/11589
    """

    c = TestClient(light=True)
    common = textwrap.dedent("""
        from conan import ConanFile
        def mycommon():
            return 42
        class Common(ConanFile):
            name = "common"
            version = "0.1"
        """)
    tool = textwrap.dedent("""
        from conan import ConanFile

        class MyGenerator:
            common = None
            def __init__(self, conanfile):
                self.conanfile = conanfile
            def generate(self):
                self.conanfile.output.info("VALUE TOOL: {}!!!".format(MyGenerator.common.mycommon()))

        class Tool(ConanFile):
            name = "tool"
            version = "0.1"
            python_requires = "common/0.1"
            def init(self):
                MyGenerator.common = self.python_requires["common"].module
        """)
    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            python_requires = "tool/0.1", "common/0.1"
            def generate(self):
                mycommon = self.python_requires["common"].module.mycommon
                self.output.info("VALUE COMMON: {}!!!".format(mycommon()))
                mygenerator = self.python_requires["tool"].module.MyGenerator(self)
                mygenerator.generate()
        """)
    c.save({"common/conanfile.py": common,
            "tool/conanfile.py": tool,
            "consumer/conanfile.py": consumer})
    c.run("export common")
    c.run("export tool")
    c.run("install consumer")
    assert "VALUE COMMON: 42!!!" in c.out
    assert "VALUE TOOL: 42!!!" in c.out


class TestTestPackagePythonRequire:
    def test_test_package_python_requires(self):
        """ test how to test_package a python_require
        """

        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            def mycommon():
                return 42
            class Common(ConanFile):
                name = "common"
                version = "0.1"
                package_type = "python-require"
            """)
        test = textwrap.dedent("""
            from conan import ConanFile

            class Tool(ConanFile):
                python_requires = "tested_reference_str"
                def test(self):
                    self.output.info("{}!!!".format(self.python_requires["common"].module.mycommon()))
            """)
        c.save({"conanfile.py": conanfile,
                "test_package/conanfile.py": test})
        c.run("create .")
        assert "common/0.1 (test package): 42!!!" in c.out

        c.run("test test_package common/0.1")
        assert "common/0.1 (test package): 42!!!" in c.out

    def test_test_package_python_requires_configs(self):
        """ test how to test_package a python_require with various configurations
        """

        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            def mycommon(build_type):
                return str(build_type).upper() + "OK"
            class Common(ConanFile):
                name = "common"
                version = "0.1"
                package_type = "python-require"
            """)
        test = textwrap.dedent("""
            from conan import ConanFile

            class Tool(ConanFile):
                settings = "build_type"
                def test(self):
                    result = self.python_requires["common"].module.mycommon(self.settings.build_type)
                    self.output.info("{}!!!".format(result))
            """)
        c.save({"conanfile.py": conanfile,
                "test_package/conanfile.py": test})
        c.run("create . ")
        assert "common/0.1 (test package): RELEASEOK!!!" in c.out
        assert "WARN: deprecated: test_package/conanfile.py should declare 'python_requires" in c.out
        c.run("create . -s build_type=Debug")
        assert "common/0.1 (test package): DEBUGOK!!!" in c.out


class TestResolveRemote:
    def test_resolve_remote_export(self):
        """ a "conan export" command should work even when a python_requires
        is in the server
        """
        c = TestClient(light=True, default_server_user=True)
        c.save({"common/conanfile.py": GenConanfile("tool", "0.1"),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("tool/0.1")})
        c.run("export common")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        c.run("create pkg")
        assert "tool/0.1: Downloaded recipe" in c.out

        c.run("remove * -c")
        c.run("export pkg")
        assert "tool/0.1: Downloaded recipe" in c.out

        c.run("remove * -c")
        c.run("export pkg -r=default")
        assert "tool/0.1: Downloaded recipe" in c.out

        c.run("remove * -c")
        c.run("create pkg -r=default")
        assert "tool/0.1: Downloaded recipe" in c.out

    def test_missing_python_require_error(self):
        """ make sure the error is clear enough for users UX
        """
        c = TestClient(light=True)
        c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("tool/0.1")})
        c.run("create pkg", assert_error=True)
        assert "Cannot resolve python_requires 'tool/0.1'" in c.out


class TestTransitiveExtend:
    # https://github.com/conan-io/conan/issues/10511
    # https://github.com/conan-io/conan/issues/10565
    def test_transitive_extend(self):
        client = TestClient(light=True)
        company = textwrap.dedent("""
            from conan import ConanFile
            class CompanyConanFile(ConanFile):
                name = "company"
                version = "1.0"

                def msg1(self):
                    return "company"
                def msg2(self):
                    return "company"
            """)
        project = textwrap.dedent("""
            from conan import ConanFile
            class ProjectBaseConanFile(ConanFile):
                name = "project"
                version = "1.0"

                python_requires = "company/1.0"
                python_requires_extend = "company.CompanyConanFile"

                def msg1(self):
                    return "project"
            """)
        consumer = textwrap.dedent("""
            from conan import ConanFile
            class Base(ConanFile):
                name = "consumer"
                version = "1.0"
                python_requires = "project/1.0"
                python_requires_extend = "project.ProjectBaseConanFile"
                def generate(self):
                    self.output.info("Msg1:{}!!!".format(self.msg1()))
                    self.output.info("Msg2:{}!!!".format(self.msg2()))
                """)
        client.save({"company/conanfile.py": company,
                     "project/conanfile.py": project,
                     "consumer/conanfile.py": consumer})
        client.run("export company")
        client.run("export project")
        client.run("install consumer")
        assert "conanfile.py (consumer/1.0): Msg1:project!!!" in client.out
        assert "conanfile.py (consumer/1.0): Msg2:company!!!" in client.out

    def test_transitive_extend2(self):
        client = TestClient(light=True)
        company = textwrap.dedent("""
            from conan import ConanFile
            class CompanyConanFile(ConanFile):
                name = "company"
                version = "1.0"

            class CompanyBase:
                def msg1(self):
                    return "company"
                def msg2(self):
                    return "company"
            """)
        project = textwrap.dedent("""
            from conan import ConanFile
            class ProjectBase:
                def msg1(self):
                    return "project"

            class ProjectBaseConanFile(ConanFile):
                name = "project"
                version = "1.0"
                python_requires = "company/1.0"

                def init(self):
                    pkg_name, base_class_name = "company", "CompanyBase"
                    base_class = getattr(self.python_requires[pkg_name].module, base_class_name)
                    global ProjectBase
                    ProjectBase = type('ProjectBase', (ProjectBase, base_class, object), {})
            """)
        consumer = textwrap.dedent("""
            from conan import ConanFile
            class Base(ConanFile):
                name = "consumer"
                version = "1.0"
                python_requires = "project/1.0"
                python_requires_extend = "project.ProjectBase"
                def generate(self):
                    self.output.info("Msg1:{}!!!".format(self.msg1()))
                    self.output.info("Msg2:{}!!!".format(self.msg2()))
                """)
        client.save({"company/conanfile.py": company,
                     "project/conanfile.py": project,
                     "consumer/conanfile.py": consumer})
        client.run("export company")
        client.run("export project")
        client.run("install consumer")
        assert "conanfile.py (consumer/1.0): Msg1:project!!!" in client.out
        assert "conanfile.py (consumer/1.0): Msg2:company!!!" in client.out


def test_multi_top_missing_from_remote():
    """
    https://github.com/conan-io/conan/issues/13656
    """
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"conanfile.py": GenConanfile("base", "1.1")})
    tc.run("create . --user=user --channel=testing")

    tc.save({"conanfile.py": GenConanfile("dep", "1.0")
            .with_python_requires("base/1.1@user/testing")})
    tc.run("create . --user=user --channel=testing -r default")

    tc.run("upload * -c -r default")
    tc.run("remove * -c")

    tc.save({"conanfile.py": GenConanfile("pkg", "1.0")
            .with_python_requires("dep/1.0@user/testing")})

    # This used to crash, with errors about not defining remotes
    tc.run("create . --name=pkg --version=1.0 -r default")

    # Ensure we found them in the remote
    assert "dep/1.0@user/testing: Not found in local cache, looking in remotes..." in tc.out
    assert "dep/1.0@user/testing: Downloaded recipe revision" in tc.out
    assert "base/1.1@user/testing: Not found in local cache, looking in remotes..." in tc.out
    assert "base/1.1@user/testing: Downloaded recipe revision" in tc.out


def test_transitive_range_not_found_in_cache():
    """
    https://github.com/conan-io/conan/issues/13761
    """
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("pr", "1.0")})
    c.run("create .")

    c.save({"conanfile.py": GenConanfile("dep", "1.0").with_python_requires("pr/[>0]")})
    c.run("create .")

    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0")})
    c.run("create . ")
    c.assert_listed_require({"pr/1.0": "Cache"}, python=True)
    assert "pr/[>0]: pr/1.0" in c.out


def test_export_pkg():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("pytool", "0.1").with_package_type("python-require")})
    c.run("export-pkg .", assert_error=True)
    assert "export-pkg can only be used for binaries, not for 'python-require'" in c.out
    # Make sure nothing is exported
    c.run("list *")
    assert "WARN: There are no matching recipe references" in c.out
    assert "pytool/0.1" not in c.out


def test_py_requires_override_method():
    tc = TestClient(light=True)
    pyreq = textwrap.dedent("""
        from conan import ConanFile
        class MyConanfileBase:
            def get_toolchain(self):
                return "mybasetoolchain"

            def generate(self):
                self.output.info("MyConanfileBase generate with value %s" % self.get_toolchain())

        class MyConanfile(ConanFile):
            name = "myconanfile"
            version = "1.0"
            package_type = "python-require"
    """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class MyConanfile(ConanFile):
            name = "app"
            version = "1.0"
            python_requires = "myconanfile/1.0"
            python_requires_extend = "myconanfile.MyConanfileBase"
            def get_toolchain(self):
                return "mycustomtoolchain"
    """)
    tc.save({"myconanfile/conanfile.py": pyreq,
             "conanfile.py": conanfile})
    tc.run("create myconanfile")
    tc.run("create .")
    assert "MyConanfileBase generate with value mycustomtoolchain" in tc.out
