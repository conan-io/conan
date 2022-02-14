import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestOtherCommands:

    def test_creation(self):
        """ there is no reason to really block commands and operations over editable packages
        except for others doing an install that depends on the editable
        """
        t = TestClient(default_server_user=True)
        t.save({'conanfile.py': GenConanfile("lib", "0.1"),
                "test_package/conanfile.py": GenConanfile().with_test("pass")})
        t.run('editable add . lib/0.1')

        # Nothing in the cache
        t.run("list recipes *")
        assert "There are no matching recipe references" in t.out
        t.run('list packages lib/0.1')
        assert "There are no recipes" in t.out

        t.run('export . ')
        assert "lib/0.1: Exported revision" in t.out
        t.run("list recipes *")
        assert "lib/0.1" in t.out
        t.run('list packages lib/0.1')
        assert "There are no packages" in t.out  # One binary is listed

        t.run('export-pkg .')
        assert "lib/0.1: Calling package()" in t.out

        t.run('list packages lib/0.1')
        assert "lib/0.1" in t.out  # One binary is listed

        t.run('upload lib/0.1 -r default')
        assert "Uploading lib/0.1" in t.out

        t.run("remove * -f")
        # Nothing in the cache
        t.run("list recipes *")
        assert "There are no matching recipe references" in t.out
        t.run('list packages lib/0.1')
        assert "There are no recipes" in t.out

    def test_consumer(self):
        """ there is no reason to really block commands and operations over editable packages
        except for others doing an install that depends on the editable
        """
        t = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           class Pkg(ConanFile):
               name = "lib"
               version = "0.1"
               def build(self):
                   self.output.info("MYBUILDFOLDER: {}".format(self.build_folder))
               """)
        t.save({'conanfile.py': conanfile,
                "test_package/conanfile.py": GenConanfile().with_test("pass"),
                "consumer/conanfile.txt": "[requires]\nlib/0.1"})
        t.run('editable add . lib/0.1')

        t.run("create .")
        t.assert_listed_require({"lib/0.1": "Editable"})
        t.assert_listed_binary({"lib/0.1": ("357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                                            "EditableBuild")})
        assert f"lib/0.1: MYBUILDFOLDER: {t.current_folder}" in t.out

        t.run("install consumer --build")
        t.assert_listed_require({"lib/0.1": "Editable"})
        t.assert_listed_binary({"lib/0.1": ("357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                                            "EditableBuild")})
        assert f"lib/0.1: MYBUILDFOLDER: {t.current_folder}" in t.out
