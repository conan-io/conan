from conans.client.loader import load_class_without_python_requires
from conans.model.conan_file import get_scm_data


def get_recipe_revision(conan_ref, client_cache):
    conanfile_path = client_cache.conanfile(conan_ref)
    conanfile = load_class_without_python_requires(conanfile_path)
    scm_data = get_scm_data(conanfile)
    if scm_data:
        return scm_data.recipe_revision
    try:
        return client_cache.load_manifest(conan_ref).summary_hash
    except:  # Workspace, not conanmanifest.txt
        return None


def get_package_revision(package_ref, client_cache):
    return client_cache.package_summary_hash(package_ref)
