from conans.client.loader_parse import load_conanfile_class
from conans.model.ref import PackageReference
import os


def download_binaries(reference, package_ids, client_cache, remote_manager, remote, output, recorder):
    conanfile_path = client_cache.conanfile(reference)
    if not os.path.exists(conanfile_path):
        raise Exception("Download recipe first")
    conanfile = load_conanfile_class(conanfile_path)
    short_paths = conanfile.short_paths

    for package_id in package_ids:
        package_ref = PackageReference(reference, package_id)
        package_folder = client_cache.package(package_ref, short_paths=short_paths)
        output.info("Downloading %s" % str(package_ref))
        remote_manager.get_package(package_ref, package_folder, remote, output, recorder)
