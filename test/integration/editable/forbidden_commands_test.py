import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestOtherCommands:

    def test_commands_not_blocked(self):
        """ there is no reason to really block commands and operations over editable packages
        except for others doing an install that depends on the editable
        """
        t = TestClient(default_server_user=True)
        t.save({'conanfile.py': GenConanfile("lib", "0.1"),
                "test_package/conanfile.py": GenConanfile().with_test("pass")})
        t.run('editable add .')

        # Nothing in the cache
        t.run("list *")
        assert "There are no matching recipe references" in t.out
        t.run('list lib/0.1:*')
        assert "ERROR: Recipe 'lib/0.1' not found" in t.out

        t.run('export . ')
        assert "lib/0.1: Exported" in t.out
        t.run("list *")
        assert "lib/0.1" in t.out
        t.run('list lib/0.1:*')
        assert "PID:" not in t.out  # One binary is listed

        t.run('export-pkg .')
        assert "lib/0.1: Exporting package" in t.out

        t.run('list lib/0.1:*')
        assert "lib/0.1" in t.out  # One binary is listed

        t.run('upload lib/0.1 -r default')
        assert "Uploading recipe 'lib/0.1" in t.out

        t.run("remove * -c")
        # Nothing in the cache
        t.run("list *")
        assert "There are no matching recipe references" in t.out
        t.run('list lib/0.1:*')
        assert "ERROR: Recipe 'lib/0.1' not found" in t.out

    def test_create_editable(self):
        """
        test that an editable can be built with conan create
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
        t.run('editable add .')

        t.run("list *")
        assert "There are no matching" in t.out

        t.run("create .")
        package_id = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        t.assert_listed_require({"lib/0.1": "Editable"})
        t.assert_listed_binary({"lib/0.1": (package_id,
                                            "EditableBuild")})
        assert f"lib/0.1: MYBUILDFOLDER: {t.current_folder}" in t.out
        t.run("list *")
        assert "lib/0.1" in t.out  # Because the create actually exports, TODO: avoid exporting?

        t.run("install consumer --build=*")
        t.assert_listed_require({"lib/0.1": "Editable"})
        t.assert_listed_binary({"lib/0.1": (package_id,
                                            "EditableBuild")})
        assert f"lib/0.1: MYBUILDFOLDER: {t.current_folder}" in t.out

        t.run("install consumer --build=editable")
        t.assert_listed_require({"lib/0.1": "Editable"})
        t.assert_listed_binary({"lib/0.1": (package_id,
                                            "EditableBuild")})
        assert f"lib/0.1: MYBUILDFOLDER: {t.current_folder}" in t.out
