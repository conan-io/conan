import os
import shutil

from conan.tools.files import copy
from conan.api.output import ConanOutput
from conan.tools.scm import Git
from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.manifest import FileTreeManifest
from conans.model.recipe_ref import RecipeReference
from conans.paths import DATA_YML
from conans.util.files import is_dirty, rmdir, set_dirty, mkdir, clean_dirty, chdir


def cmd_export(app, global_conf, conanfile_path, name, version, user, channel, graph_lock=None,
               remotes=None):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    loader, cache, hook_manager = app.loader, app.cache, app.hook_manager
    conanfile = loader.load_export(conanfile_path, name, version, user, channel, graph_lock,
                                   remotes=remotes)

    ref = RecipeReference(conanfile.name, conanfile.version,  conanfile.user, conanfile.channel)
    ref.validate_ref(allow_uppercase=global_conf.get("core:allow_uppercase_pkg_names",
                                                     check_type=bool))

    conanfile.conf = global_conf.get_conanfile_conf(ref, is_consumer=True)
    conanfile.display_name = str(ref)
    conanfile.output.scope = conanfile.display_name
    scoped_output = conanfile.output

    recipe_layout = cache.create_export_recipe_layout(ref)

    hook_manager.execute("pre_export", conanfile=conanfile)

    scoped_output.info(f"Exporting package recipe: {conanfile_path}")

    export_folder = recipe_layout.export()
    export_src_folder = recipe_layout.export_sources()
    # TODO: cache2.0 move this creation to other place
    mkdir(export_folder)
    mkdir(export_src_folder)
    recipe_metadata = recipe_layout.metadata()
    mkdir(recipe_metadata)
    conanfile.folders.set_base_recipe_metadata(recipe_metadata)
    export_recipe(conanfile, export_folder)
    export_source(conanfile, export_src_folder)
    shutil.copy2(conanfile_path, recipe_layout.conanfile())

    # Execute post-export hook before computing the digest
    hook_manager.execute("post_export", conanfile=conanfile)
    conanfile.folders.set_base_export(None)
    conanfile.folders.set_base_export_sources(None)

    # Compute the new digest
    manifest = FileTreeManifest.create(export_folder, export_src_folder)
    manifest.save(export_folder)
    manifest.report_summary(scoped_output)

    # Compute the revision for the recipe
    revision = _calc_revision(scoped_output=conanfile.output,
                              path=os.path.dirname(conanfile_path),
                              manifest=manifest,
                              revision_mode=conanfile.revision_mode,
                              conanfile=conanfile)

    ref.revision = revision
    recipe_layout.reference = ref
    cache.assign_rrev(recipe_layout)
    scoped_output.info('Exported to cache folder: %s' % recipe_layout.export())

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
                                "for deletion", error_type="exception")
            scoped_output.warning(str(e))
            set_dirty(source_folder)

    scoped_output.success(f"Exported: {ref.repr_humantime()}")
    return ref, conanfile


def _calc_revision(scoped_output, path, manifest, revision_mode, conanfile):
    if revision_mode not in ["scm", "scm_folder", "hash"]:
        raise ConanException("Revision mode should be one of 'hash' (default) or 'scm'")

    # Use the proper approach depending on 'revision_mode'
    if revision_mode == "hash":
        revision = manifest.summary_hash
    else:
        # Exception to the rule that tools should only be used in recipes, this Git helper is ok
        excluded = getattr(conanfile, "revision_mode_excluded", None)
        git = Git(conanfile, folder=path, excluded=excluded)
        try:
            revision = git.get_commit(repository=(revision_mode == "scm"))
        except Exception as exc:
            error_msg = "Cannot detect revision using '{}' mode from repository at " \
                        "'{}'".format(revision_mode, path)
            raise ConanException("{}: {}".format(error_msg, exc))

        if git.is_dirty():
            raise ConanException("Can't have a dirty repository using revision_mode='scm' and doing"
                                 " 'conan export', please commit the changes and run again, or "
                                 "use 'git_excluded = []' attribute")

        scoped_output.info("Using git commit as the recipe revision: %s" % revision)

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


def export_source(conanfile, destination_source_folder):
    if callable(conanfile.exports_sources):
        raise ConanException("conanfile 'exports_sources' shouldn't be a method, "
                             "use 'export_sources()' instead")

    if isinstance(conanfile.exports_sources, str):
        conanfile.exports_sources = (conanfile.exports_sources,)

    included_sources, excluded_sources = _classify_patterns(conanfile.exports_sources)
    for pattern in included_sources:
        copy(conanfile, pattern, src=conanfile.recipe_folder,
             dst=destination_source_folder, excludes=excluded_sources)

    conanfile.folders.set_base_export_sources(destination_source_folder)
    _run_method(conanfile, "export_sources")


def export_recipe(conanfile, destination_folder):
    if callable(conanfile.exports):
        raise ConanException("conanfile 'exports' shouldn't be a method, use 'export()' instead")
    if isinstance(conanfile.exports, str):
        conanfile.exports = (conanfile.exports,)

    package_output = ConanOutput(scope="%s: exports" % conanfile.output.scope)

    if os.path.exists(os.path.join(conanfile.recipe_folder, DATA_YML)):
        package_output.info("File '{}' found. Exporting it...".format(DATA_YML))
        tmp = [DATA_YML]
        if conanfile.exports:
            tmp.extend(conanfile.exports)  # conanfile.exports could be a tuple (immutable)
        conanfile.exports = tmp

    included_exports, excluded_exports = _classify_patterns(conanfile.exports)

    for pattern in included_exports:
        copy(conanfile, pattern, conanfile.recipe_folder, destination_folder,
             excludes=excluded_exports)

    conanfile.folders.set_base_export(destination_folder)
    _run_method(conanfile, "export")


def _run_method(conanfile, method):
    export_method = getattr(conanfile, method, None)
    if export_method:
        if not callable(export_method):
            raise ConanException("conanfile '%s' must be a method" % method)

        conanfile.output.highlight("Calling %s()" % method)
        default_options = conanfile.default_options
        options = conanfile.options
        try:
            # TODO: Poor man attribute control access. Convert to nice decorator
            conanfile.default_options = None
            conanfile.options = None
            with chdir(conanfile.recipe_folder):
                with conanfile_exception_formatter(conanfile, method):
                    export_method()
        finally:
            conanfile.default_options = default_options
            conanfile.options = options
