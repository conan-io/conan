from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


def get_package_ref(name, version, username, channel, package_id, revision, p_revision):
    ref = RecipeReference(name, version, username, channel, revision)
    return PkgReference(ref, package_id, p_revision)
