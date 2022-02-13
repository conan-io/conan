import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class ForbiddenRemoveTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_remove(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class APck(ConanFile):
                pass
            """)
        ref = RecipeReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': conanfile,
                      "mylayout": "", })
        t.run("export . --name=lib --version=version --user=user --channel=name")
        t.run('editable add . {}'.format(ref))
        self.assertTrue(t.cache.installed_as_editable(ref))
        t.run('remove {} --force'.format(ref), assert_error=True)
        self.assertIn("Package 'lib/version@user/name' is installed as editable, remove it first "
                      "using command 'conan editable remove lib/version@user/name'", t.out)

        # Also with a pattern, but only a warning
        t.run('remove lib* --force')
        self.assertIn("WARN: Package 'lib/version@user/name' is installed as editable, "
                      "remove it first using command 'conan editable remove lib/version@user/name'",
                      t.out)
        self.assertTrue(t.cache.installed_as_editable(ref))


class TestOtherCommands:

    def test_creation(self):
        """ there is no reason to really block commands and operations over editable packages
        except for others doing an install that depends on the editable
        """
        t = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "lib"
                version = "0.1"
                def build(self):
                    self.output.info("FOLDER: {}".format(self.build_folder))
                """)
        t.save({'conanfile.py': conanfile,
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

        # TODO: What a create over an editable should do?
        t.run('create . ')
        print(t.out)
        t.run('list packages lib/0.1')
        assert "lib/0.1" in t.out  # One binary is listed

        t.run('upload lib/0.1 -r default')
        assert "Uploading lib/0.1" in t.out

        t.run('export-pkg .')
        assert "lib/0.1: Calling package()" in t.out

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
                   self.output.info("FOLDER: {}".format(self.build_folder))
               """)
        t.save({'conanfile.py': conanfile,
                "test_package/conanfile.py": GenConanfile().with_test("pass"),
                "consumer/conanfile.txt": "[requires]\nlib/0.1"})
        t.run('editable add . lib/0.1')

        t.run("install consumer --build")
        print(t.out)
