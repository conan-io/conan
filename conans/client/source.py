import os
import shutil

import six

from conans.client import tools
from conans.client.cmd.export import export_recipe, export_source
from conans.errors import ConanException, ConanExceptionInUserConanfileMethod, \
    conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.scm import SCM, get_scm_data
from conans.paths import CONANFILE, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME
from conans.util.conan_v2_mode import conan_v2_property
from conans.util.files import (is_dirty, mkdir, rmdir, set_dirty_context_manager,
                               merge_directories, clean_dirty)


def retrieve_exports_sources(remote_manager, cache, conanfile, ref, remotes):
    """ the "exports_sources" sources are not retrieved unless necessary to build. In some
    occassions, conan needs to get them too, like if uploading to a server, to keep the recipes
    complete
    """
    package_layout = cache.package_layout(ref, conanfile.short_paths)
    export_sources_folder = package_layout.export_sources()
    if os.path.exists(export_sources_folder):
        return None

    if conanfile.exports_sources is None and not hasattr(conanfile, "export_sources"):
        mkdir(export_sources_folder)
        return None

    # If not path to sources exists, we have a problem, at least an empty folder
    # should be there
    current_remote = package_layout.load_metadata().recipe.remote
    if current_remote:
        current_remote = remotes[current_remote]
    if not current_remote:
        msg = ("The '%s' package has 'exports_sources' but sources not found in local cache.\n"
               "Probably it was installed from a remote that is no longer available.\n"
               % str(ref))
        raise ConanException(msg)

    try:
        remote_manager.get_recipe_sources(ref, package_layout, current_remote)
    except Exception as e:
        msg = ("The '%s' package has 'exports_sources' but sources not found in local cache.\n"
               "Probably it was installed from a remote that is no longer available.\n"
               % str(ref))
        raise ConanException("\n".join([str(e), msg]))


def config_source_local(conanfile, conanfile_path, hook_manager):
    """ Entry point for the "conan source" command.
    """
    conanfile_folder = os.path.dirname(conanfile_path)

    def get_sources_from_exports():
        src_folder = conanfile.source_folder
        if conanfile_folder != src_folder:
            _run_local_scm(conanfile, conanfile_folder, src_folder, output=conanfile.output)
            conanfile.output.info("Executing exports to: %s" % src_folder)
            if not hasattr(conanfile, "layout"):
                export_recipe(conanfile, conanfile_folder, src_folder)
            else:
                # If layout declared, the export_sources will go to base source (like develop2)
                src_folder = conanfile.folders.base_source

            if conanfile_folder != src_folder:
                export_source(conanfile, conanfile_folder, src_folder)

    _run_source(conanfile, conanfile_path, hook_manager, reference=None, cache=None,
                get_sources_from_exports=get_sources_from_exports)


def config_source(export_folder, export_source_folder, scm_sources_folder, conanfile, output,
                  conanfile_path, reference, hook_manager, cache):
    """ Implements the sources configuration when a package is going to be built in the
    local cache:
    - remove old sources if dirty or build_policy=always
    - execute SCM logic
    - do a copy of the export and exports_sources folders to the source folder in the cache
    - run the source() recipe method
    """

    def remove_source():
        output.warn("This can take a while for big packages")
        try:
            rmdir(conanfile.folders.base_source)
        except BaseException as e_rm:
            msg = str(e_rm)
            if six.PY2:
                msg = str(e_rm).decode("latin1")  # Windows prints some chars in latin1
            output.error("Unable to remove source folder %s\n%s" %
                         (conanfile.folders.base_source, msg))
            output.warn("**** Please delete it manually ****")
            raise ConanException("Unable to remove source folder")

    if is_dirty(conanfile.folders.base_source):
        output.warn("Trying to remove corrupted source folder")
        remove_source()
        clean_dirty(conanfile.folders.base_source)
    elif conanfile.build_policy_always:
        output.warn("Detected build_policy 'always', trying to remove source folder")
        remove_source()

    if not os.path.exists(conanfile.folders.base_source):  # No source folder, need to get it
        with set_dirty_context_manager(conanfile.folders.base_source):
            mkdir(conanfile.source_folder)

            def get_sources_from_exports():
                # First of all get the exported scm sources (if auto) or clone (if fixed)
                _run_cache_scm(conanfile, scm_sources_folder, output)
                if not hasattr(conanfile, "layout"):
                    # so self exported files have precedence over python_requires ones
                    merge_directories(export_folder, conanfile.folders.base_source)
                # Now move the export-sources to the right location
                merge_directories(export_source_folder, conanfile.folders.base_source)

            _run_source(conanfile, conanfile_path, hook_manager, reference, cache,
                        get_sources_from_exports=get_sources_from_exports)


def _run_source(conanfile, conanfile_path, hook_manager, reference, cache,
                get_sources_from_exports):
    """Execute the source core functionality, both for local cache and user space, in order:
        - Calling pre_source hook
        - Getting sources from SCM
        - Getting sources from exported folders in the local cache
        - Clean potential TGZ and other files in the local cache
        - Executing the recipe source() method
        - Calling post_source hook
    """

    src_folder = conanfile.source_folder if hasattr(conanfile, "layout") \
        else conanfile.folders.base_source
    mkdir(src_folder)

    with tools.chdir(src_folder):
        try:
            with get_env_context_manager(conanfile):
                hook_manager.execute("pre_source", conanfile=conanfile,
                                     conanfile_path=conanfile_path,
                                     reference=reference)
                output = conanfile.output
                output.info('Configuring sources in %s' % src_folder)
                get_sources_from_exports()

                if cache:
                    # Clear the conanfile.py to avoid errors cloning git repositories.
                    _clean_source_folder(src_folder)
                with conanfile_exception_formatter(conanfile.display_name, "source"):

                    with conan_v2_property(conanfile, 'settings',
                                           "'self.settings' access in source() method is deprecated"):
                        with conan_v2_property(conanfile, 'options',
                                               "'self.options' access in source() method is deprecated"):
                            conanfile.source()

                hook_manager.execute("post_source", conanfile=conanfile,
                                     conanfile_path=conanfile_path,
                                     reference=reference)
        except ConanExceptionInUserConanfileMethod:
            raise
        except Exception as e:
            raise ConanException(e)


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


def _run_cache_scm(conanfile, scm_sources_folder, output):
    """
    :param conanfile: recipe
    :param src_folder: sources folder in the cache, (Destination dir)
    :param scm_sources_folder: scm sources folder in the cache, where the scm sources were exported
    :param output: output
    :return:
    """
    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return

    if scm_data.subfolder:
        dest_dir = os.path.normpath(os.path.join(conanfile.folders.base_source, scm_data.subfolder))
    else:
        dest_dir = conanfile.folders.base_source
    if os.path.exists(scm_sources_folder):
        output.info("Copying previously cached scm sources")
        merge_directories(scm_sources_folder, dest_dir)
    else:
        output.info("SCM: Getting sources from url: '%s'" % scm_data.url)
        try:
            scm = SCM(scm_data, dest_dir, output)
            scm.checkout()
        except Exception as e:
            raise ConanException("Couldn't checkout SCM: %s" % str(e))
        # This is a bit weird. Why after a SCM should we remove files.
        # Maybe check conan 2.0
        # TODO: Why removing in the cache? There is no danger.
        _clean_source_folder(dest_dir)


def _run_local_scm(conanfile, conanfile_folder, src_folder, output):
    """
    Only called when 'conan source' in user space
    :param conanfile: recipe
    :param src_folder: specified src_folder
    :param conanfile_folder: Folder containing the local conanfile
    :param output: Output
    :return:
    """

    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return
    dest_dir = os.path.normpath(os.path.join(src_folder, scm_data.subfolder or ""))
    # In user space, if revision="auto", then copy
    if scm_data.capture_origin or scm_data.capture_revision:  # FIXME: or clause?
        scm = SCM(scm_data, conanfile_folder, output)
        scm_url = scm_data.url if scm_data.url != "auto" else \
            scm.get_qualified_remote_url(remove_credentials=True)

        src_path = scm.get_local_path_to_url(url=scm_url)
        if src_path and src_path != dest_dir:
            excluded = SCM(scm_data, src_path, output).excluded_files
            output.info("SCM: Getting sources from folder: %s" % src_path)
            merge_directories(src_path, dest_dir, excluded=excluded)
            return

    output.info("SCM: Getting sources from url: '%s'" % scm_data.url)
    scm = SCM(scm_data, dest_dir, output)
    scm.checkout()
