import os
import shutil

import six

from conans import tools
from conans.errors import ConanException, conanfile_exception_formatter, \
    ConanExceptionInUserConanfileMethod
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference
from conans.model.scm import SCM
from conans.paths import EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME, CONANFILE, CONAN_MANIFEST
from conans.util.files import rmdir, set_dirty, is_dirty, clean_dirty, mkdir, walk
from conans.model.scm import SCMData


def complete_recipe_sources(remote_manager, client_cache, registry, conanfile, conan_reference):
    sources_folder = client_cache.export_sources(conan_reference, conanfile.short_paths)
    if os.path.exists(sources_folder):
        return None

    if conanfile.exports_sources is None:
        mkdir(sources_folder)
        return None

    # If not path to sources exists, we have a problem, at least an empty folder
    # should be there
    current_remote = registry.get_recipe_remote(conan_reference)
    if not current_remote:
        raise ConanException("Error while trying to get recipe sources for %s. "
                             "No remote defined" % str(conan_reference))

    export_path = client_cache.export(conan_reference)
    remote_manager.get_recipe_sources(conan_reference, export_path, sources_folder,
                                      current_remote)


def merge_directories(src, dst, excluded=None, symlinks=True):
    dst = os.path.normpath(dst)
    excluded = excluded or []
    excluded = [os.path.normpath(entry) for entry in excluded]

    def is_excluded(origin_path):
        if origin_path == dst:
            return True
        rel_path = os.path.normpath(os.path.relpath(origin_path, src))
        if rel_path in excluded:
            return True
        return False

    for src_dir, dirs, files in walk(src, followlinks=True):
        if is_excluded(src_dir):
            dirs[:] = []
            continue

        # Overwriting the dirs will prevents walk to get into them
        files[:] = [d for d in files if not is_excluded(os.path.join(src_dir, d))]

        dst_dir = os.path.normpath(os.path.join(dst, os.path.relpath(src_dir, src)))
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.islink(src_file) and symlinks:
                linkto = os.readlink(src_file)
                os.symlink(linkto, dst_file)
            else:
                shutil.copy2(src_file, dst_file)


def _clean_source_folder(folder):
    for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME, CONANFILE+"c",
              CONANFILE+"o", CONANFILE, CONAN_MANIFEST):
        try:
            os.remove(os.path.join(folder, f))
        except OSError:
            pass


def get_scm_data(conanfile):
    try:
        return SCMData(conanfile)
    except ConanException:
        return None


def config_source(export_folder, export_source_folder, local_sources_path, src_folder,
                  conanfile, output, conanfile_path, reference, plugin_manager, force=False):
    """ creates src folder and retrieve, calling source() from conanfile
    the necessary source code
    """

    def remove_source(raise_error=True):
        output.warn("This can take a while for big packages")
        try:
            rmdir(src_folder)
        except BaseException as e_rm:
            set_dirty(src_folder)
            msg = str(e_rm)
            if six.PY2:
                msg = str(e_rm).decode("latin1")  # Windows prints some chars in latin1
            output.error("Unable to remove source folder %s\n%s" % (src_folder, msg))
            output.warn("**** Please delete it manually ****")
            if raise_error or isinstance(e_rm, KeyboardInterrupt):
                raise ConanException("Unable to remove source folder")

    if force:
        output.warn("Forced removal of source folder")
        remove_source()
    elif is_dirty(src_folder):
        output.warn("Trying to remove corrupted source folder")
        remove_source()
    elif conanfile.build_policy_always:
        output.warn("Detected build_policy 'always', trying to remove source folder")
        remove_source()
    elif local_sources_path and os.path.exists(local_sources_path):
        output.warn("Detected 'scm' auto in conanfile, trying to remove source folder")
        remove_source()

    if not os.path.exists(src_folder):
        set_dirty(src_folder)
        mkdir(src_folder)
        os.chdir(src_folder)
        conanfile.source_folder = src_folder
        try:
            with conanfile_exception_formatter(str(conanfile), "source"):
                with get_env_context_manager(conanfile):
                    conanfile.build_folder = None
                    conanfile.package_folder = None
                    plugin_manager.execute("pre_source", conanfile=conanfile,
                                           conanfile_path=conanfile_path, reference=reference)
                    output.info('Configuring sources in %s' % src_folder)
                    scm_data = get_scm_data(conanfile)
                    if scm_data:
                        dest_dir = os.path.normpath(os.path.join(src_folder, scm_data.subfolder))
                        captured = local_sources_path and os.path.exists(local_sources_path)
                        local_sources_path = local_sources_path if captured else None
                        _fetch_scm(scm_data, dest_dir, local_sources_path, output)

                    merge_directories(export_folder, src_folder)
                    # Now move the export-sources to the right location
                    merge_directories(export_source_folder, src_folder)
                    _clean_source_folder(src_folder)
                    try:
                        shutil.rmtree(os.path.join(src_folder, "__pycache__"))
                    except OSError:
                        pass

                    conanfile.source()
                    plugin_manager.execute("post_source", conanfile=conanfile,
                                           conanfile_path=conanfile_path,  reference=reference)
            clean_dirty(src_folder)  # Everything went well, remove DIRTY flag
        except Exception as e:
            os.chdir(export_folder)
            # in case source() fails (user error, typically), remove the src_folder
            # and raise to interrupt any other processes (build, package)
            output.warn("Trying to remove corrupted source folder")
            remove_source(raise_error=False)
            if isinstance(e, ConanExceptionInUserConanfileMethod):
                raise e
            raise ConanException(e)


def config_source_local(dest_dir, conanfile, conanfile_folder, output, conanfile_path,
                        plugin_manager):
    conanfile.source_folder = dest_dir
    conanfile.build_folder = None
    conanfile.package_folder = None
    with tools.chdir(dest_dir):
        try:
            with conanfile_exception_formatter(str(conanfile), "source"):
                with get_env_context_manager(conanfile):
                    plugin_manager.execute("pre_source", conanfile=conanfile,
                                           conanfile_path=conanfile_path)
                    output.info('Configuring sources in %s' % dest_dir)
                    scm_data = get_scm_data(conanfile)
                    if scm_data:
                        dest_dir = os.path.join(dest_dir, scm_data.subfolder)
                        capture = scm_data.capture_origin or scm_data.capture_revision
                        local_sources_path = conanfile_folder if capture else None
                        _fetch_scm(scm_data, dest_dir, local_sources_path, output)

                    conanfile.source()
                    plugin_manager.execute("post_source", conanfile=conanfile,
                                           conanfile_path=conanfile_path)
        except ConanExceptionInUserConanfileMethod:
            raise
        except Exception as e:
            raise ConanException(e)


def _fetch_scm(scm_data, dest_dir, local_sources_path, output):
    if local_sources_path:
        excluded = SCM(scm_data, local_sources_path).excluded_files
        output.info("Getting sources from folder: %s" % local_sources_path)
        merge_directories(local_sources_path, dest_dir, excluded=excluded)
    else:
        output.info("Getting sources from url: '%s'" % scm_data.url)
        scm = SCM(scm_data, dest_dir)
        scm.checkout()
    _clean_source_folder(dest_dir)
