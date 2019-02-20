import os
import shutil

from conans.client.source import complete_recipe_sources
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import rmdir


def _prepare_sources(cache, ref, remote_manager, loader):
    conan_file_path = cache.conanfile(ref)
    conanfile = loader.load_class(conan_file_path)
    complete_recipe_sources(remote_manager, cache, conanfile, ref)
    return conanfile.short_paths


def _get_package_ids(cache, ref, package_ids):
    if not package_ids:
        return []
    if package_ids is True:
        packages = cache.packages(ref)
        if os.path.exists(packages):
            package_ids = os.listdir(packages)
        else:
            package_ids = []
    return package_ids


def cmd_copy(ref, user_channel, package_ids, cache, user_io, remote_manager, loader, force=False):
    """
    param package_ids: Falsey=do not copy binaries. True=All existing. []=list of ids
    """
    # It is important to get the revision early, so "complete_recipe_sources" can
    # get the right revision sources, not latest
    src_metadata = cache.package_layout(ref).load_metadata()
    ref = ref.copy_with_rev(src_metadata.recipe.revision)
    short_paths = _prepare_sources(cache, ref, remote_manager, loader)
    package_ids = _get_package_ids(cache, ref, package_ids)
    package_copy(ref, user_channel, package_ids, cache, user_io, short_paths, force)


def package_copy(src_ref, user_channel, package_ids, paths, user_io, short_paths=False, force=False):
    dest_ref = ConanFileReference.loads("%s/%s@%s" % (src_ref.name,
                                                      src_ref.version,
                                                      user_channel))
    # Generate metadata
    src_metadata = paths.package_layout(src_ref).load_metadata()

    # Copy export
    export_origin = paths.export(src_ref)
    if not os.path.exists(export_origin):
        raise ConanException("'%s' doesn't exist" % str(src_ref))
    export_dest = paths.export(dest_ref)
    if os.path.exists(export_dest):
        if not force and not user_io.request_boolean("'%s' already exist. Override?"
                                                     % str(dest_ref)):
            return
        rmdir(export_dest)
    shutil.copytree(export_origin, export_dest, symlinks=True)
    user_io.out.info("Copied %s to %s" % (str(src_ref), str(dest_ref)))

    export_sources_origin = paths.export_sources(src_ref, short_paths)
    export_sources_dest = paths.export_sources(dest_ref, short_paths)
    if os.path.exists(export_sources_dest):
        rmdir(export_sources_dest)
    shutil.copytree(export_sources_origin, export_sources_dest, symlinks=True)
    user_io.out.info("Copied sources %s to %s" % (str(src_ref), str(dest_ref)))

    # Copy packages
    package_revisions = {}  # To be stored in the metadata
    for package_id in package_ids:
        pref_origin = PackageReference(src_ref, package_id)
        pref_dest = PackageReference(dest_ref, package_id)
        package_path_origin = paths.package(pref_origin, short_paths)
        package_path_dest = paths.package(pref_dest, short_paths)
        if os.path.exists(package_path_dest):
            if not force and not user_io.request_boolean("Package '%s' already exist."
                                                         " Override?" % str(package_id)):
                continue
            rmdir(package_path_dest)
        package_revisions[package_id] = (src_metadata.packages[package_id].revision,
                                         src_metadata.recipe.revision)
        shutil.copytree(package_path_origin, package_path_dest, symlinks=True)
        user_io.out.info("Copied %s to %s" % (str(package_id), str(dest_ref)))

    # Generate the metadata
    with paths.package_layout(dest_ref).update_metadata() as metadata:
        metadata.recipe.revision = src_metadata.recipe.revision
        for package_id, (revision, recipe_revision) in package_revisions.items():
            metadata.packages[package_id].revision = revision
            metadata.packages[package_id].recipe_revision = recipe_revision
