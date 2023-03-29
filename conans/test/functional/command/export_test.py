import os

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.scm import git_add_changes_commit
from conans.test.utils.tools import TestClient


class TestExportMetadataTest:

    @pytest.mark.tool("git")
    def test_revision_mode_scm(self):
        t = TestClient()
        conanfile = str(GenConanfile().with_class_attribute('revision_mode = "scm"'))
        commit = t.init_git_repo({'conanfile.py': conanfile})

        t.run(f"export . --name=pkg --version=0.1")

        ref = RecipeReference.loads("pkg/0.1")
        latest_rev = t.cache.get_latest_recipe_reference(ref)
        assert latest_rev.revision == commit

    @pytest.mark.tool("git")
    def test_revision_mode_scm_subfolder(self):
        t = TestClient()
        conanfile = str(GenConanfile().with_class_attribute('revision_mode = "scm"'))
        commit = t.init_git_repo({'pkga/conanfile.py': conanfile,
                                  'pkgb/conanfile.py': conanfile})

        t.save({"pkgb/conanfile.py": conanfile + "\n#comment"})
        commit_b = git_add_changes_commit(os.path.join(t.current_folder, "pkgb"), msg="fix")

        t.run(f"export pkga --name=pkga --version=0.1")
        ref = RecipeReference.loads("pkga/0.1")
        latest_rev = t.cache.get_latest_recipe_reference(ref)
        assert latest_rev.revision == commit

        t.run(f"export pkgb --name=pkgb --version=0.1")
        ref = RecipeReference.loads("pkgb/0.1")
        latest_rev = t.cache.get_latest_recipe_reference(ref)
        assert latest_rev.revision == commit_b
