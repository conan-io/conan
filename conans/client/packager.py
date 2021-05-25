import os

from conans.client.file_copier import FileCopier, report_copied_files
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO
from conans.util.files import mkdir, save


def export_pkg(conanfile, package_id, src_package_folder, hook_manager, conanfile_path, ref):

    # NOTE: The layout folder is not taken into account for the cache, it is not useful to introduce
    #       a subfolder there.
    mkdir(conanfile.package_folder)

    output = conanfile.output
    output.info("Exporting to cache existing package from user folder")
    output.info("Package folder %s" % conanfile.package_folder)
    hook_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    copier = FileCopier([src_package_folder], conanfile.package_folder)
    copier("*", symlinks=True)

    hook_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    save(os.path.join(conanfile.package_folder, CONANINFO), conanfile.info.dumps())
    manifest = FileTreeManifest.create(conanfile.package_folder)
    manifest.save(conanfile.package_folder)
    report_files_from_manifest(output, manifest)

    output.success("Package '%s' created" % package_id)

    prev = manifest.summary_hash
    output.info("Created package revision %s" % prev)
    return prev


def update_package_metadata(prev, layout, package_id, rrev):
    with layout.update_metadata() as metadata:
        metadata.packages[package_id].revision = prev
        metadata.packages[package_id].recipe_revision = rrev


def report_files_from_manifest(output, manifest):
    copied_files = list(manifest.files())
    copied_files.remove(CONANINFO)

    if not copied_files:
        output.warn("No files in this package!")
        return

    report_copied_files(copied_files, output, message_suffix="Packaged")
