import os
import shutil

import six

from conans.client import tools
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.conan_file import get_env_context_manager
from conans.model.scm import SCM, get_scm_data
from conans.paths import CONANFILE, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME
from conans.util.files import (clean_dirty, is_dirty, load, mkdir, rmdir, set_dirty,
                               merge_directories)


def complete_recipe_sources(remote_manager, cache, conanfile, ref):
    """ the "exports_sources" sources are not retrieved unless necessary to build. In some
    occassions, conan needs to get them too, like if uploading to a server, to keep the recipes
    complete
    """
    sources_folder = cache.export_sources(ref, conanfile.short_paths)
    if os.path.exists(sources_folder):
        return None

    if conanfile.exports_sources is None:
        mkdir(sources_folder)
        return None

    # If not path to sources exists, we have a problem, at least an empty folder
    # should be there
    current_remote = cache.registry.refs.get(ref)
    if not current_remote:
        raise ConanException("Error while trying to get recipe sources for %s. "
                             "No remote defined" % str(ref))

    export_path = cache.export(ref)
    remote_manager.get_recipe_sources(ref, export_path, sources_folder, current_remote)


def config_source_local(src_folder, conanfile, conanfile_path, hook_manager):
    """ Entry point for the "conan source" command.
    """
    class PackageLocalLayout(object):
        ref = None

        def __init__(self, base_folder):
            self._base_folder = base_folder

        def base_folder(self):
            return self._base_folder

        def conanfile(self):
            return os.path.join(self._base_folder, CONANFILE)

    conanfile_folder = os.path.dirname(conanfile_path)
    package_layout = PackageLocalLayout(base_folder=conanfile_folder)
    _run_source(conanfile, package_layout, src_folder, hook_manager, conanfile_folder)


def config_source(package_layout, conanfile, output, hook_manager, cache):
    """ Implements the sources configuration when a package is going to be built in the
    local cache.
    """
    src_folder = package_layout.source()

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

    sources_pointer = package_layout.scm_folder()
    local_sources_path = load(sources_pointer) if os.path.exists(sources_pointer) else None
    if is_dirty(src_folder):
        output.warn("Trying to remove corrupted source folder")
        remove_source()
    elif conanfile.build_policy_always:
        output.warn("Detected build_policy 'always', trying to remove source folder")
        remove_source()
    elif local_sources_path and os.path.exists(local_sources_path):
        output.warn("Detected 'scm' auto in conanfile, trying to remove source folder")
        remove_source()

    if not os.path.exists(src_folder):  # No source folder, need to get it
        set_dirty(src_folder)
        mkdir(src_folder)
        _run_source(conanfile, package_layout, src_folder, hook_manager, local_sources_path)
        clean_dirty(src_folder)  # Everything went well, remove DIRTY flag


def _run_source(conanfile, package_layout, src_folder, hook_manager, local_sources_path):
    """Execute the source core functionality, both for local cache and user space, in order:
        - Calling pre_source hook
        - Getting sources from SCM
        - Getting sources from exported folders in the local cache
        - Clean potential TGZ and other files in the local cache
        - Executing the recipe source() method
        - Calling post_source hook
    """
    conanfile.source_folder = src_folder
    conanfile.build_folder = None
    conanfile.package_folder = None
    with tools.chdir(src_folder):
        try:
            with get_env_context_manager(conanfile):
                hook_manager.execute("pre_source", conanfile=conanfile,
                                     conanfile_path=package_layout.conanfile(),
                                     reference=package_layout.ref)  # TODO: .ref is None for local workflow
                output = conanfile.output
                output.info('Configuring sources in %s' % src_folder)

                in_cache = not isinstance(package_layout, PackageLocalLayout)  # TODO: What about editables?
                _run_scm(conanfile, src_folder, local_sources_path, output, in_cache=in_cache)

                if in_cache:
                    _get_sources_from_exports(src_folder, package_layout)
                    _clean_source_folder(src_folder)
                with conanfile_exception_formatter(conanfile.display_name, "source"):
                    conanfile.source()

                hook_manager.execute("post_source", conanfile=conanfile,
                                     conanfile_path=package_layout.conanfile(),
                                     reference=package_layout.ref)
        except ConanExceptionInUserConanfileMethod:
            raise
        except Exception as e:
            raise ConanException(e)


def _get_sources_from_exports(src_folder, package_layout):
    # so self exported files have precedence over python_requires ones
    merge_directories(package_layout.export(), src_folder)
    # Now move the export-sources to the right location
    merge_directories(package_layout.export_sources(), src_folder)


def _clean_source_folder(folder):
    for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME, CONANFILE+"c",
              CONANFILE+"o", CONANFILE, CONAN_MANIFEST):
        try:
            os.remove(os.path.join(folder, f))
        except OSError:
            pass
    try:
        shutil.rmtree(os.path.join(folder, "__pycache__"))
    except OSError:
        pass


def _run_scm(conanfile, src_folder, local_sources_path, output, in_cache):
    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return

    dest_dir = os.path.normpath(os.path.join(src_folder, scm_data.subfolder))
    if in_cache:
        # When in cache, capturing the sources from user space is done only if exists
        if not local_sources_path or not os.path.exists(local_sources_path):
            local_sources_path = None
    else:
        # In user space, if revision="auto", then copy
        if scm_data.capture_origin or scm_data.capture_revision:  # FIXME: or clause?
            scm = SCM(scm_data, local_sources_path, output)
            scm_url = scm_data.url if scm_data.url != "auto" else \
                scm.get_qualified_remote_url(remove_credentials=True)

            src_path = scm.get_local_path_to_url(url=scm_url)
            if src_path:
                local_sources_path = src_path
        else:
            local_sources_path = None

    if local_sources_path and conanfile.develop:
        excluded = SCM(scm_data, local_sources_path, output).excluded_files
        output.info("Getting sources from folder: %s" % local_sources_path)
        merge_directories(local_sources_path, dest_dir, excluded=excluded)
    else:
        output.info("Getting sources from url: '%s'" % scm_data.url)
        scm = SCM(scm_data, dest_dir, output)
        scm.checkout()

    if in_cache:
        # This is a bit weird. Why after a SCM should we remove files. Maybe check conan 2.0
        _clean_source_folder(dest_dir)
