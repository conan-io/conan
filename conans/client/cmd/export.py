import ast
import os
import shutil
import sys

import six
import yaml

from conans.client.file_copier import FileCopier
from conans.client.output import Color, ScopedOutput
from conans.client.remover import DiskRemover
from conans.client.tools import chdir
from conans.errors import ConanException, ConanV2Exception, conanfile_exception_formatter
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference
from conans.model.scm import SCM, get_scm_data
from conans.paths import CONANFILE, DATA_YML
from conans.search.search import search_recipes, search_packages
from conans.util.conan_v2_mode import conan_v2_error
from conans.util.files import is_dirty, load, rmdir, save, set_dirty, remove, mkdir, \
    merge_directories, clean_dirty
from conans.util.log import logger

isPY38 = bool(sys.version_info.major == 3 and sys.version_info.minor == 8)


def export_alias(package_layout, target_ref, output, revisions_enabled):
    revision_mode = "hash"
    conanfile = """
from conans import ConanFile

class AliasConanfile(ConanFile):
    alias = "%s"
    revision_mode = "%s"
""" % (target_ref.full_str(), revision_mode)

    save(package_layout.conanfile(), conanfile)
    manifest = FileTreeManifest.create(package_layout.export())
    manifest.save(folder=package_layout.export())

    # Create the metadata for the alias
    _update_revision_in_metadata(package_layout=package_layout, revisions_enabled=revisions_enabled,
                                 output=output, path=None, manifest=manifest,
                                 revision_mode=revision_mode)


def check_casing_conflict(cache, ref):
    # Check for casing conflict
    # Maybe a platform check could be added, but depends on disk partition
    refs = search_recipes(cache, ref, ignorecase=True)
    refs2 = [ConanFileReference(r.name, r.version, r.user if ref.user else None,
                                r.channel if ref.channel else None, validate=False) for r in refs]

    if refs and ref not in refs2:
        raise ConanException("Cannot export package with same name but different case\n"
                             "You exported '%s' but already existing '%s'"
                             % (str(ref), " ".join(str(s) for s in refs)))


def cmd_export(app, conanfile_path, name, version, user, channel, keep_source,
               export=True, graph_lock=None, ignore_dirty=False):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    loader, cache, hook_manager, output = app.loader, app.cache, app.hook_manager, app.out
    revisions_enabled = app.config.revisions_enabled
    scm_to_conandata = app.config.scm_to_conandata
    conanfile = loader.load_export(conanfile_path, name, version, user, channel)

    # FIXME: Conan 2.0, deprecate CONAN_USER AND CONAN_CHANNEL and remove this try excepts
    # Take the default from the env vars if they exist to not break behavior
    try:
        user = conanfile.user
    except ConanV2Exception:
        raise
    except ConanException:
        user = None

    try:
        channel = conanfile.channel
    except ConanV2Exception:
        raise
    except ConanException:
        channel = None

    ref = ConanFileReference(conanfile.name, conanfile.version, user, channel)
    conanfile.display_name = str(ref)
    conanfile.output.scope = conanfile.display_name

    # If we receive lock information, python_requires could have been locked
    if graph_lock:
        node_id = graph_lock.get_consumer(ref)
        python_requires = graph_lock.python_requires(node_id)
        # TODO: check that the locked python_requires are different from the loaded ones
        app.range_resolver.clear_output()  # invalidate previous version range output
        conanfile = loader.load_export(conanfile_path, conanfile.name, conanfile.version,
                                       ref.user, ref.channel, python_requires)

    check_casing_conflict(cache=cache, ref=ref)
    package_layout = cache.package_layout(ref, short_paths=conanfile.short_paths)
    if not export:
        metadata = package_layout.load_metadata()
        recipe_revision = metadata.recipe.revision
        ref = ref.copy_with_rev(recipe_revision)
        if graph_lock:
            graph_lock.update_exported_ref(node_id, ref)
        return ref

    _check_settings_for_warnings(conanfile, output)

    hook_manager.execute("pre_export", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=package_layout.ref)
    logger.debug("EXPORT: %s" % conanfile_path)

    output.highlight("Exporting package recipe")
    output = conanfile.output

    # Copy sources to target folders
    with package_layout.conanfile_write_lock(output=output):
        # Get previous manifest
        try:
            previous_manifest = package_layout.recipe_manifest()
        except IOError:
            previous_manifest = None

        package_layout.export_remove()
        export_folder = package_layout.export()
        export_src_folder = package_layout.export_sources()
        mkdir(export_folder)
        mkdir(export_src_folder)
        origin_folder = os.path.dirname(conanfile_path)
        export_recipe(conanfile, origin_folder, export_folder)
        export_source(conanfile, origin_folder, export_src_folder)
        shutil.copy2(conanfile_path, package_layout.conanfile())

        # Calculate the "auto" values and replace in conanfile.py
        scm_data, local_src_folder = _capture_scm_auto_fields(conanfile,
                                                              os.path.dirname(conanfile_path),
                                                              package_layout, output,
                                                              ignore_dirty, scm_to_conandata)
        # Clear previous scm_folder
        modified_recipe = False
        scm_sources_folder = package_layout.scm_sources()
        if local_src_folder and not keep_source:
            # Copy the local scm folder to scm_sources in the cache
            mkdir(scm_sources_folder)
            _export_scm(scm_data, local_src_folder, scm_sources_folder, output)
            # https://github.com/conan-io/conan/issues/5195#issuecomment-551840597
            # It will cause the source folder to be removed (needed because the recipe still has
            # the "auto" with uncommitted changes)
            modified_recipe = True

        # Execute post-export hook before computing the digest
        hook_manager.execute("post_export", conanfile=conanfile, reference=package_layout.ref,
                             conanfile_path=package_layout.conanfile())

        # Compute the new digest
        manifest = FileTreeManifest.create(export_folder, export_src_folder)
        modified_recipe |= not previous_manifest or previous_manifest != manifest
        if modified_recipe:
            output.success('A new %s version was exported' % CONANFILE)
            output.info('Folder: %s' % export_folder)
        else:
            output.info("The stored package has not changed")
            manifest = previous_manifest  # Use the old one, keep old timestamp
        manifest.save(export_folder)

    # Compute the revision for the recipe
    revision = _update_revision_in_metadata(package_layout=package_layout,
                                            revisions_enabled=revisions_enabled,
                                            output=output,
                                            path=os.path.dirname(conanfile_path),
                                            manifest=manifest,
                                            revision_mode=conanfile.revision_mode)

    # FIXME: Conan 2.0 Clear the registry entry if the recipe has changed
    source_folder = package_layout.source()
    if os.path.exists(source_folder):
        try:
            if is_dirty(source_folder):
                output.info("Source folder is corrupted, forcing removal")
                rmdir(source_folder)
                clean_dirty(source_folder)
            elif modified_recipe and not keep_source:
                output.info("Package recipe modified in export, forcing source folder removal")
                output.info("Use the --keep-source, -k option to skip it")
                rmdir(source_folder)
        except BaseException as e:
            output.error("Unable to delete source folder. Will be marked as corrupted for deletion")
            output.warn(str(e))
            set_dirty(source_folder)

    # When revisions enabled, remove the packages not matching the revision
    if revisions_enabled:
        packages = search_packages(package_layout, query=None)
        metadata = package_layout.load_metadata()
        recipe_revision = metadata.recipe.revision
        to_remove = [pid for pid in packages if
                     metadata.packages.get(pid) and
                     metadata.packages.get(pid).recipe_revision != recipe_revision]
        if to_remove:
            output.info("Removing the local binary packages from different recipe revisions")
            remover = DiskRemover()
            remover.remove_packages(package_layout, ids_filter=to_remove)

    ref = ref.copy_with_rev(revision)
    output.info("Exported revision: %s" % revision)
    if graph_lock:
        graph_lock.update_exported_ref(node_id, ref)
    return ref


def _check_settings_for_warnings(conanfile, output):
    if not conanfile.settings:
        return
    try:
        if 'os_build' not in conanfile.settings:
            return
        if 'os' not in conanfile.settings:
            return

        output.writeln("*" * 60, front=Color.BRIGHT_RED)
        output.writeln("  This package defines both 'os' and 'os_build' ",
                       front=Color.BRIGHT_RED)
        output.writeln("  Please use 'os' for libraries and 'os_build'",
                       front=Color.BRIGHT_RED)
        output.writeln("  only for build-requires used for cross-building",
                       front=Color.BRIGHT_RED)
        output.writeln("*" * 60, front=Color.BRIGHT_RED)
    except ConanException:
        pass


def _capture_scm_auto_fields(conanfile, conanfile_dir, package_layout, output, ignore_dirty,
                             scm_to_conandata):
    """Deduce the values for the scm auto fields or functions assigned to 'url' or 'revision'
       and replace the conanfile.py contents.
       Returns a tuple with (scm_data, path_to_scm_local_directory)"""
    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return None, None

    # Resolve SCMData in the user workspace (someone may want to access CVS or import some py)
    scm = SCM(scm_data, conanfile_dir, output)
    captured = scm_data.capture_origin or scm_data.capture_revision

    if not captured:
        # We replace not only "auto" values, also evaluated functions (e.g from a python_require)
        _replace_scm_data_in_recipe(package_layout, scm_data, scm_to_conandata)
        return scm_data, None

    if not scm.is_pristine() and not ignore_dirty:
        output.warn("There are uncommitted changes, skipping the replacement of 'scm.url' and "
                    "'scm.revision' auto fields. Use --ignore-dirty to force it. The 'conan "
                    "upload' command will prevent uploading recipes with 'auto' values in these "
                    "fields.")
        origin = scm.get_qualified_remote_url(remove_credentials=True)
        local_src_path = scm.get_local_path_to_url(origin)
        return scm_data, local_src_path

    if scm_data.url == "auto":
        origin = scm.get_qualified_remote_url(remove_credentials=True)
        if not origin:
            output.warn("Repo origin cannot be deduced, 'auto' fields won't be replaced."
                        " 'conan upload' command will prevent uploading recipes with 'auto'"
                        " values in these fields.")
            local_src_path = scm.get_local_path_to_url(origin)
            return scm_data, local_src_path
        if scm.is_local_repository():
            output.warn("Repo origin looks like a local path: %s" % origin)
        output.success("Repo origin deduced by 'auto': %s" % origin)
        scm_data.url = origin

    if scm_data.revision == "auto":
        # If it is pristine by default we don't replace the "auto" unless forcing
        # This prevents the recipe to get uploaded pointing to an invalid commit
        scm_data.revision = scm.get_revision()
        output.success("Revision deduced by 'auto': %s" % scm_data.revision)

    local_src_path = scm.get_local_path_to_url(scm_data.url)
    _replace_scm_data_in_recipe(package_layout, scm_data, scm_to_conandata)

    return scm_data, local_src_path


def _replace_scm_data_in_recipe(package_layout, scm_data, scm_to_conandata):
    if scm_to_conandata:
        conandata_path = os.path.join(package_layout.export(), DATA_YML)
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
    else:
        conan_v2_error("general.scm_to_conandata should be set to 1")
        _replace_scm_data_in_conanfile(package_layout.conanfile(), scm_data)


def _replace_scm_data_in_conanfile(conanfile_path, scm_data):
    # FIXME: Remove in Conan 2.0, it will use conandata.yml as the only way
    # Parsing and replacing the SCM field
    content = load(conanfile_path)
    headers = []

    if six.PY2:
        # Workaround for https://bugs.python.org/issue22221
        lines_without_headers = []
        lines = content.splitlines(True)
        for line in lines:
            if not lines_without_headers and line.startswith("#"):
                headers.append(line)
            else:
                lines_without_headers.append(line)
        content = ''.join(lines_without_headers)

    lines = content.splitlines(True)
    tree = ast.parse(content)
    to_replace = []
    comments = []
    class_line = None
    tab_size = 4
    for i_body, item in enumerate(tree.body):
        if isinstance(item, ast.ClassDef):
            statements = item.body
            class_line = item.lineno
            for i, stmt in enumerate(item.body):
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    line = lines[stmt.lineno - 1]
                    tab_size = len(line) - len(line.lstrip())
                    if isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "scm":
                        try:
                            if i + 1 == len(statements):  # Last statement in my ClassDef
                                if i_body + 1 == len(tree.body):  # Last statement over all
                                    next_line = len(lines)
                                else:
                                    next_line = tree.body[i_body + 1].lineno - 1
                            else:
                                # Next statement can be a comment or anything else
                                next_statement = statements[i + 1]
                                if isPY38 and isinstance(next_statement, ast.Expr):
                                    # Python 3.8 properly parses multiline comments with start
                                    # and end lines, here we preserve the same (wrong)
                                    # implementation of previous releases
                                    next_line = next_statement.end_lineno - 1
                                else:
                                    next_line = next_statement.lineno - 1
                                next_line_content = lines[next_line].strip()
                                if (next_line_content.endswith('"""') or
                                    next_line_content.endswith("'''")):
                                    next_line += 1
                        except IndexError:
                            next_line = stmt.lineno
                        replace = [line for line in lines[(stmt.lineno - 1):next_line]]
                        to_replace.append("".join(replace).lstrip())
                        comments = [line.strip('\n') for line in replace
                                    if line.strip().startswith("#") or not line.strip()]
                        break

    if len(to_replace) > 1:
        raise ConanException("The conanfile.py defines more than one class level 'scm' attribute")

    new_text = "scm = " + ",\n          ".join(str(scm_data).split(",")) + "\n"

    if len(to_replace) == 0:
        # SCM exists, but not found in the conanfile, probably inherited from superclass
        # FIXME: This will inject the lines only the latest class declared in the conanfile
        tmp = lines[0:class_line]
        tmp.append("{}{}".format(" " * tab_size, new_text))
        tmp.extend(lines[class_line:])
        content = ''.join(tmp)
    else:
        if comments:
            new_text += '\n'.join(comments) + "\n"
        content = content.replace(to_replace[0], new_text)
        content = content if not headers else ''.join(headers) + content

    remove(conanfile_path)
    save(conanfile_path, content)


def _detect_scm_revision(path):
    if not path:
        raise ConanException("Not path supplied")

    repo_type = SCM.detect_scm(path)
    if not repo_type:
        raise ConanException("'{}' repository not detected".format(repo_type))

    repo_obj = SCM.availables.get(repo_type)(path)
    return repo_obj.get_revision(), repo_type, repo_obj.is_pristine()


def _update_revision_in_metadata(package_layout, revisions_enabled, output, path, manifest,
                                 revision_mode):
    if revision_mode not in ["scm", "hash"]:
        raise ConanException("Revision mode should be one of 'hash' (default) or 'scm'")

    # Use the proper approach depending on 'revision_mode'
    if revision_mode == "hash":
        revision = manifest.summary_hash
        if revisions_enabled:
            output.info("Using the exported files summary hash as the recipe"
                        " revision: {} ".format(revision))
    else:
        try:
            rev_detected, repo_type, is_pristine = _detect_scm_revision(path)
        except Exception as exc:
            error_msg = "Cannot detect revision using '{}' mode from repository at " \
                        "'{}'".format(revision_mode, path)
            raise ConanException("{}: {}".format(error_msg, exc))

        revision = rev_detected

        if revisions_enabled:
            output.info("Using %s commit as the recipe revision: %s" % (repo_type, revision))
            if not is_pristine:
                output.warn("Repo status is not pristine: there might be modified files")

    with package_layout.update_metadata() as metadata:
        metadata.recipe.revision = revision

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


def _export_scm(scm_data, origin_folder, scm_sources_folder, output):
    """ Copy the local folder to the scm_sources folder in the cache, this enables to work
        with local sources without committing and pushing changes to the scm remote.
        https://github.com/conan-io/conan/issues/5195"""
    excluded = SCM(scm_data, origin_folder, output).excluded_files
    excluded.append("conanfile.py")
    output.info("SCM: Getting sources from folder: %s" % origin_folder)
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

    conanfile.folders.set_base_export_sources(destination_source_folder)
    _run_method(conanfile, "export_sources", origin_folder, destination_source_folder, output)
    conanfile.folders.set_base_export_sources(None)


def export_recipe(conanfile, origin_folder, destination_folder):
    if callable(conanfile.exports):
        raise ConanException("conanfile 'exports' shouldn't be a method, use 'export()' instead")
    if isinstance(conanfile.exports, str):
        conanfile.exports = (conanfile.exports,)

    output = conanfile.output
    package_output = ScopedOutput("%s exports" % output.scope, output)

    if os.path.exists(os.path.join(origin_folder, DATA_YML)):
        package_output.info("File '{}' found. Exporting it...".format(DATA_YML))
        tmp = [DATA_YML]
        if conanfile.exports:
            tmp.extend(conanfile.exports)  # conanfile.exports could be a tuple (immutable)
        conanfile.exports = tmp

    included_exports, excluded_exports = _classify_patterns(conanfile.exports)

    try:
        os.unlink(os.path.join(origin_folder, CONANFILE + 'c'))
    except OSError:
        pass

    copier = FileCopier([origin_folder], destination_folder)
    for pattern in included_exports:
        copier(pattern, links=True, excludes=excluded_exports)
    copier.report(package_output)

    conanfile.folders.set_base_export(destination_folder)
    _run_method(conanfile, "export", origin_folder, destination_folder, output)
    conanfile.folders.set_base_export(None)


def _run_method(conanfile, method, origin_folder, destination_folder, output):
    export_method = getattr(conanfile, method, None)
    if export_method:
        if not callable(export_method):
            raise ConanException("conanfile '%s' must be a method" % method)
        output.highlight("Calling %s()" % method)
        copier = FileCopier([origin_folder], destination_folder)
        conanfile.copy = copier
        default_options = conanfile.default_options
        try:
            # TODO: Poor man attribute control access. Convert to nice decorator
            conanfile.default_options = None
            with chdir(origin_folder):
                with conanfile_exception_formatter(str(conanfile), method):
                    export_method()
        finally:
            conanfile.default_options = default_options
        export_method_output = ScopedOutput("%s %s() method" % (output.scope, method), output)
        copier.report(export_method_output)
