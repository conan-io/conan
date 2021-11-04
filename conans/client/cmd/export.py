import os
import shutil

import yaml

from conan.cache.conan_reference import ConanReference
from conans.cli.output import Color, ConanOutput
from conans.cli.output import ScopedOutput
from conans.client.file_copier import FileCopier
from conans.client.tools import chdir
from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference
from conans.model.scm import SCM, get_scm_data
from conans.paths import CONANFILE, DATA_YML
from conans.util.files import is_dirty, load, rmdir, save, set_dirty, mkdir, \
    merge_directories, clean_dirty
from conans.util.log import logger


def export_alias(alias_ref, target_ref, cache):
    revision_mode = "hash"
    conanfile = """
from conans import ConanFile

class AliasConanfile(ConanFile):
    alias = "%s"
    revision_mode = "%s"
""" % (target_ref.full_str(), revision_mode)

    alias_layout = cache.create_export_recipe_layout(alias_ref)

    save(alias_layout.conanfile(), conanfile)
    manifest = FileTreeManifest.create(alias_layout.export())
    manifest.save(folder=alias_layout.export())

    rrev = calc_revision(scoped_output=ConanOutput(),
                         path=None, manifest=manifest, revision_mode=revision_mode)

    ref_with_rrev = alias_ref.copy_with_rev(rrev)
    alias_layout.reference = ConanReference(ref_with_rrev)
    cache.assign_rrev(alias_layout)


def cmd_export(app, conanfile_path, name, version, user, channel, graph_lock=None,
               ignore_dirty=False):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    loader, cache, hook_manager = app.loader, app.cache, app.hook_manager
    conanfile = loader.load_export(conanfile_path, name, version, user, channel, graph_lock)

    ref = ConanFileReference(conanfile.name, conanfile.version,  conanfile.user, conanfile.channel)
    conanfile.display_name = str(ref)
    conanfile.output.scope = conanfile.display_name
    scoped_output = conanfile.output

    recipe_layout = cache.create_export_recipe_layout(ref)

    hook_manager.execute("pre_export", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref)
    logger.debug("EXPORT: %s" % conanfile_path)

    scoped_output.highlight("Exporting package recipe")

    export_folder = recipe_layout.export()
    export_src_folder = recipe_layout.export_sources()
    # TODO: cache2.0 move this creation to other place
    mkdir(export_folder)
    mkdir(export_src_folder)
    origin_folder = os.path.dirname(conanfile_path)
    export_recipe(conanfile, origin_folder, export_folder)
    export_source(conanfile, origin_folder, export_src_folder)
    shutil.copy2(conanfile_path, recipe_layout.conanfile())

    # Calculate the "auto" values and replace in conanfile.py
    scm_data, local_src_folder = _capture_scm_auto_fields(conanfile,
                                                          os.path.dirname(conanfile_path),
                                                          recipe_layout,
                                                          ignore_dirty)

    scm_sources_folder = recipe_layout.scm_sources()
    if local_src_folder:
        # Copy the local scm folder to scm_sources in the cache
        mkdir(scm_sources_folder)
        _export_scm(conanfile.output, scm_data, local_src_folder, scm_sources_folder)

    # Execute post-export hook before computing the digest
    hook_manager.execute("post_export", conanfile=conanfile, reference=ref,
                         conanfile_path=recipe_layout.conanfile())

    # Compute the new digest
    manifest = FileTreeManifest.create(export_folder, export_src_folder)
    manifest.save(export_folder)

    # Compute the revision for the recipe
    revision = calc_revision(scoped_output=conanfile.output,
                             path=os.path.dirname(conanfile_path),
                             manifest=manifest,
                             revision_mode=conanfile.revision_mode)

    ref = ref.copy_with_rev(revision=revision)
    recipe_layout.reference = ConanReference(ref)
    cache.assign_rrev(recipe_layout)
    # TODO: cache2.0 check if this is the message we want to output
    scoped_output.success('A new %s version was exported' % CONANFILE)
    scoped_output.info('Folder: %s' % recipe_layout.export())

    # FIXME: Conan 2.0 Clear the registry entry if the recipe has changed
    # TODO: cache2.0: check this part
    source_folder = recipe_layout.source()
    if os.path.exists(source_folder):
        try:
            if is_dirty(source_folder):
                scoped_output.info("Source folder is corrupted, forcing removal")
                rmdir(source_folder)
                clean_dirty(source_folder)
        except BaseException as e:
            scoped_output.error("Unable to delete source folder. Will be marked as corrupted "
                                "for deletion")
            scoped_output.warning(str(e))
            set_dirty(source_folder)

    scoped_output.info("Exported revision: %s" % revision)
    if graph_lock is not None:
        graph_lock.update_lock_export_ref(ref)

    return ref


def _capture_scm_auto_fields(conanfile, conanfile_dir, recipe_layout, ignore_dirty):
    """Deduce the values for the scm auto fields or functions assigned to 'url' or 'revision'
       and replace the conanfile.py contents.
       Returns a tuple with (scm_data, path_to_scm_local_directory)"""
    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return None, None

    # Resolve SCMData in the user workspace (someone may want to access CVS or import some py)
    scm = SCM(scm_data, conanfile_dir, conanfile.output)
    captured = scm_data.capture_origin or scm_data.capture_revision

    if not captured:
        # We replace not only "auto" values, also evaluated functions (e.g from a python_require)
        _replace_scm_data_in_recipe(recipe_layout, scm_data)
        return scm_data, None

    if not scm.is_pristine() and not ignore_dirty:
        conanfile.output.warning("There are uncommitted changes, skipping the replacement of 'scm.url' and "
                                "'scm.revision' auto fields. Use --ignore-dirty to force it. The 'conan "
                       "upload' command will prevent uploading recipes with 'auto' values in these "
                       "fields.")
        origin = scm.get_qualified_remote_url(remove_credentials=True)
        local_src_path = scm.get_local_path_to_url(origin)
        return scm_data, local_src_path

    if scm_data.url == "auto":
        origin = scm.get_qualified_remote_url(remove_credentials=True)
        if not origin:
            conanfile.output.warning(
                "Repo origin cannot be deduced, 'auto' fields won't be replaced."
                " 'conan upload' command will prevent uploading recipes with 'auto'"
                " values in these fields.")
            local_src_path = scm.get_local_path_to_url(origin)
            return scm_data, local_src_path
        if scm.is_local_repository():
            conanfile.output.warning("Repo origin looks like a local path: %s" % origin)
        conanfile.output.success("Repo origin deduced by 'auto': %s" % origin)
        scm_data.url = origin

    if scm_data.revision == "auto":
        # If it is pristine by default we don't replace the "auto" unless forcing
        # This prevents the recipe to get uploaded pointing to an invalid commit
        scm_data.revision = scm.get_revision()
        conanfile.output.success("Revision deduced by 'auto': %s" % scm_data.revision)

    local_src_path = scm.get_local_path_to_url(scm_data.url)
    _replace_scm_data_in_recipe(recipe_layout, scm_data)

    return scm_data, local_src_path


def _replace_scm_data_in_recipe(recipe_layout, scm_data):
    conandata_path = os.path.join(recipe_layout.export(), DATA_YML)
    conandata_yml = {}
    if os.path.exists(conandata_path):
        conandata_yml = yaml.safe_load(load(conandata_path))
        conandata_yml = conandata_yml or {}  # In case the conandata is a blank file
        if '.conan' in conandata_yml:
            raise ConanException("Field '.conan' inside '{}' file is reserved to "
                                 "Conan usage.".format(DATA_YML))
    scm_data_copied = scm_data.as_dict()
    scm_data_copied.pop('username', None)
    scm_data_copied.pop('password', None)
    conandata_yml['.conan'] = {'scm': scm_data_copied}
    save(conandata_path, yaml.safe_dump(conandata_yml, default_flow_style=False))


def _detect_scm_revision(path):
    if not path:
        raise ConanException("Not path supplied")

    repo_type = SCM.detect_scm(path)
    if not repo_type:
        raise ConanException("'{}' repository not detected".format(repo_type))

    repo_obj = SCM.availables.get(repo_type)(path)
    return repo_obj.get_revision(), repo_type, repo_obj.is_pristine()


def calc_revision(scoped_output, path, manifest, revision_mode):
    if revision_mode not in ["scm", "hash"]:
        raise ConanException("Revision mode should be one of 'hash' (default) or 'scm'")

    # Use the proper approach depending on 'revision_mode'
    if revision_mode == "hash":
        revision = manifest.summary_hash
        scoped_output.info("Using the exported files summary hash as the recipe"
                           " revision: {} ".format(revision))
    else:
        try:
            rev_detected, repo_type, is_pristine = _detect_scm_revision(path)
        except Exception as exc:
            error_msg = "Cannot detect revision using '{}' mode from repository at " \
                        "'{}'".format(revision_mode, path)
            raise ConanException("{}: {}".format(error_msg, exc))

        revision = rev_detected

        scoped_output.info("Using %s commit as the recipe revision: %s" % (repo_type, revision))
        if not is_pristine:
            scoped_output.warning("Repo status is not pristine: there might be modified files")

    return revision


def _classify_patterns(patterns):
    patterns = patterns or []
    included, excluded = [], []
    for p in patterns:
        if p.startswith("!"):
            excluded.append(p[1:])
        else:
            included.append(p)
    return included, excluded


def _export_scm(scoped_output, scm_data, origin_folder, scm_sources_folder):
    """ Copy the local folder to the scm_sources folder in the cache, this enables to work
        with local sources without committing and pushing changes to the scm remote.
        https://github.com/conan-io/conan/issues/5195"""
    excluded = SCM(scm_data, origin_folder, scoped_output).excluded_files
    excluded.append("conanfile.py")
    scoped_output.info("SCM: Getting sources from folder: %s" % origin_folder)
    merge_directories(origin_folder, scm_sources_folder, excluded=excluded)


def export_source(conanfile, origin_folder, destination_source_folder):
    if callable(conanfile.exports_sources):
        raise ConanException("conanfile 'exports_sources' shouldn't be a method, "
                             "use 'export_sources()' instead")

    if isinstance(conanfile.exports_sources, str):
        conanfile.exports_sources = (conanfile.exports_sources,)

    included_sources, excluded_sources = _classify_patterns(conanfile.exports_sources)
    copier = FileCopier([origin_folder], destination_source_folder)
    for pattern in included_sources:
        copier(pattern, links=True, excludes=excluded_sources)
    output = conanfile.output
    package_output = ScopedOutput("%s exports_sources" % output.scope, output)
    copier.report(package_output)

    _run_method(conanfile, "export_sources", origin_folder, destination_source_folder)


def export_recipe(conanfile, origin_folder, destination_folder):
    if callable(conanfile.exports):
        raise ConanException("conanfile 'exports' shouldn't be a method, use 'export()' instead")
    if isinstance(conanfile.exports, str):
        conanfile.exports = (conanfile.exports,)

    scoped_output = conanfile.output
    package_output = ScopedOutput("%s exports" % scoped_output.scope, scoped_output)

    if os.path.exists(os.path.join(origin_folder, DATA_YML)):
        package_output.info("File '{}' found. Exporting it...".format(DATA_YML))
        tmp = [DATA_YML]
        if conanfile.exports:
            tmp.extend(conanfile.exports)  # conanfile.exports could be a tuple (immutable)
        conanfile.exports = tmp

    included_exports, excluded_exports = _classify_patterns(conanfile.exports)

    copier = FileCopier([origin_folder], destination_folder)
    for pattern in included_exports:
        copier(pattern, links=True, excludes=excluded_exports)
    copier.report(package_output)

    _run_method(conanfile, "export", origin_folder, destination_folder)


def _run_method(conanfile, method, origin_folder, destination_folder):
    export_method = getattr(conanfile, method, None)
    if export_method:
        if not callable(export_method):
            raise ConanException("conanfile '%s' must be a method" % method)
        conanfile.output.highlight("Calling %s()" % method)
        copier = FileCopier([origin_folder], destination_folder)
        conanfile.copy = copier
        folder_name = "%s_folder" % method
        setattr(conanfile, folder_name, destination_folder)
        default_options = conanfile.default_options
        try:
            # TODO: Poor man attribute control access. Convert to nice decorator
            conanfile.default_options = None
            with chdir(origin_folder):
                with conanfile_exception_formatter(str(conanfile), method):
                    export_method()
        finally:
            conanfile.default_options = default_options
            delattr(conanfile, folder_name)
        export_method_output = ScopedOutput("%s %s() method" % (conanfile.output.scope, method),
                                            conanfile.output)
        copier.report(export_method_output)
