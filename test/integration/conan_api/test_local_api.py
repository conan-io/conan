import os

from conan.api.conan_api import ConanAPI
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.internal.model.recipe_ref import RecipeReference
from conans.util.files import save


def test_local_api():
    # https://github.com/conan-io/conan/issues/17484
    current_folder = temp_folder()
    cache_folder = temp_folder()
    save(os.path.join(current_folder, "conanfile.py"), str(GenConanfile("foo", "1.0")))
    api = ConanAPI(cache_folder)
    assert api.local.editable_packages.edited_refs == {}
    api.local.editable_add(".", cwd=current_folder)
    assert list(api.local.editable_packages.edited_refs) == [RecipeReference.loads("foo/1.0")]
