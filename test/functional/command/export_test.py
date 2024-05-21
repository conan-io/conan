import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import git_add_changes_commit
from conan.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.tool("git")
class TestRevisionModeSCM:

    def test_revision_mode_scm(self):
        t = TestClient()
        conanfile = str(GenConanfile().with_class_attribute('revision_mode = "scm"'))
        commit = t.init_git_repo({'conanfile.py': conanfile})

        t.run(f"export . --name=pkg --version=0.1")
        assert t.exported_recipe_revision() == commit

        # Now it will fail if dirty
        t.save({"conanfile.py": conanfile + "\n#comment"})
        t.run(f"export . --name=pkg --version=0.1", assert_error=True)
        assert "Can't have a dirty repository using revision_mode='scm' and doing" in t.out
        # Commit to fix
        commit2 = git_add_changes_commit(t.current_folder, msg="fix")
        t.run(f"export . --name=pkg --version=0.1")
        assert t.exported_recipe_revision() == commit2

    def test_revision_mode_scm_subfolder(self):
        """ emulates a mono-repo with 2 subprojects, when a change is done in a subproject
        it gets a different folder commit
        """
        t = TestClient()
        conanfile = str(GenConanfile().with_class_attribute('revision_mode = "scm_folder"'))
        commit = t.init_git_repo({'pkga/conanfile.py': conanfile,
                                  'pkgb/conanfile.py': conanfile})

        t.save({"pkgb/conanfile.py": conanfile + "\n#comment"})
        commit_b = git_add_changes_commit(os.path.join(t.current_folder, "pkgb"), msg="fix")

        # pkga still gets the initial commit, as it didn't change its contents
        t.run(f"export pkga --name=pkga --version=0.1")
        assert t.exported_recipe_revision() == commit

        # but pkgb will get the commit of the new changed folder
        t.run(f"export pkgb --name=pkgb --version=0.1")
        assert t.exported_recipe_revision() == commit_b

        # if pkgb is dirty, we should still be able to correctly create pkga in 'scm_folder' mode
        t.save({"pkgb/conanfile.py": conanfile + "\n#new comment"})
        t.run(f"export pkga --name=pkga --version=0.1")
        assert t.exported_recipe_revision() == commit

    def test_auto_revision_without_commits(self):
        """If we have a repo but without commits, it has to fail when the revision_mode=scm"""
        t = TestClient()
        t.run_command('git init .')
        t.save({"conanfile.py": GenConanfile("lib", "0.1").with_revision_mode("scm")})
        t.run("export .", assert_error=True)
        # It errors, because no commits yet
        assert "Cannot detect revision using 'scm' mode from repository" in t.out

    @pytest.mark.parametrize("conf_excluded, recipe_excluded",
                             [("", ["*.cpp", "*.txt", "src/*"]),
                              (["*.cpp", "*.txt", "src/*"], ""),
                              ('+["*.cpp", "*.txt"]', ["src/*"]),
                              ('+["*.cpp"]', ["*.txt", "src/*"])])
    def test_revision_mode_scm_excluded_files(self, conf_excluded, recipe_excluded):
        t = TestClient()
        recipe_excluded = f'revision_mode_excluded = {recipe_excluded}' if recipe_excluded else ""
        conf_excluded = f'core.scm:excluded={conf_excluded}' if conf_excluded else ""
        save(t.cache.global_conf_path, conf_excluded)
        conanfile = GenConanfile("pkg", "0.1").with_class_attribute('revision_mode = "scm"') \
                                              .with_class_attribute(recipe_excluded)
        commit = t.init_git_repo({'conanfile.py': str(conanfile),
                                  "test.cpp": "mytest"})

        t.run(f"export .")
        assert t.exported_recipe_revision() == commit

        t.save({"test.cpp": "mytest2",
                "new.txt": "new",
                "src/potato": "hello"})
        t.run(f"export . -vvv")
        assert t.exported_recipe_revision() == commit

        t.save({"test.py": ""})
        t.run(f"export .", assert_error=True)
        assert "ERROR: Can't have a dirty repository using revision_mode='scm'" in t.out
