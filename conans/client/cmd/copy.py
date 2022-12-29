import os
import shutil

from conans.client.source import retrieve_exports_sources
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import rmdir


def _prepare_sources(cache, ref, remote_manager, loader, remotes):
    conan_file_path = cache.package_layout(ref).conanfile()
    conanfile = loader.load_basic(conan_file_path)
    retrieve_exports_sources(remote_manager, cache, conanfile, ref, remotes)
    return conanfile.short_paths


def cmd_copy(ref, user_channel, package_ids, cache, user_io, remote_manager, loader, remotes,
             force=False):
    """
    param package_ids: Falsey=do not copy binaries. True=All existing. []=list of ids
    """
    # It is important to get the revision early, so "retrieve_exports_sources" can
    # get the right revision sources, not latest
    layout = cache.package_layout(ref)
    src_metadata = layout.load_metadata()
    ref = ref.copy_with_rev(src_metadata.recipe.revision)
    short_paths = _prepare_sources(cache, ref, remote_manager, loader, remotes)
    package_ids = layout.package_ids() if package_ids is True else (package_ids or [])
    package_copy(ref, user_channel, package_ids, cache, user_io, short_paths, force)


def package_copy(src_ref, user_channel, package_ids, cache, user_io, short_paths=False,
                 force=False):

    ref = "%s/%s@%s" % (src_ref.name, src_ref.version, user_channel)
    if ref.count('@') > 1:
        raise ConanException("Destination must contain user/channel only.")

    dest_ref = ConanFileReference.loads(ref)
    # Generate metadata
    src_layout = cache.package_layout(src_ref, short_paths)
    src_metadata = src_layout.load_metadata()
    dst_layout = cache.package_layout(dest_ref, short_paths)

    # Copy export
    export_origin = src_layout.export()
    if not os.path.exists(export_origin):
        raise ConanException("'%s' doesn't exist" % str(src_ref))
    export_dest = dst_layout.export()
    if os.path.exists(export_dest):
        if not force and not user_io.request_boolean("'%s' already exist. Override?"
                                                     % str(dest_ref)):
            return
        rmdir(export_dest)
    shutil.copytree(export_origin, export_dest, symlinks=True)
    user_io.out.info("Copied %s to %s" % (str(src_ref), str(dest_ref)))

    export_sources_origin = src_layout.export_sources()
    export_sources_dest = dst_layout.export_sources()
    if os.path.exists(export_sources_dest):
        rmdir(export_sources_dest)
    shutil.copytree(export_sources_origin, export_sources_dest, symlinks=True)
    user_io.out.info("Copied sources %s to %s" % (str(src_ref), str(dest_ref)))

    # Copy packages
    package_revisions = {}  # To be stored in the metadata
    for package_id in package_ids:
        pref_origin = PackageReference(src_ref, package_id)
        pref_dest = PackageReference(dest_ref, package_id)
        package_path_origin = src_layout.package(pref_origin)
        if dst_layout.package_id_exists(package_id):
            if not force and not user_io.request_boolean("Package '%s' already exist."
                                                         " Override?" % str(package_id)):
                continue
            dst_layout.package_remove(pref_dest)
        package_path_dest = dst_layout.package(pref_dest)
        package_revisions[package_id] = (src_metadata.packages[package_id].revision,
                                         src_metadata.recipe.revision)
        shutil.copytree(package_path_origin, package_path_dest, symlinks=True)
        user_io.out.info("Copied %s to %s" % (str(package_id), str(dest_ref)))

        # The downloaded .tgz files can also be copied
        src_download = src_layout.download_package(pref_origin)
        dst_download = dst_layout.download_package(pref_dest)
        rmdir(dst_download)
        if os.path.isdir(src_download):
            shutil.copytree(src_download, dst_download)

    # The downloaded export and sources .tgz files can also be copied
    src_download = src_layout.download_export()
    dst_download = dst_layout.download_export()
    rmdir(dst_download)
    if os.path.isdir(src_download):
        shutil.copytree(src_download, dst_download)

    # Generate the metadata
    with dst_layout.update_metadata() as metadata:
        metadata.recipe.revision = src_metadata.recipe.revision
        for package_id, (revision, recipe_revision) in package_revisions.items():
            metadata.packages[package_id].revision = revision
            metadata.packages[package_id].recipe_revision = recipe_revision
