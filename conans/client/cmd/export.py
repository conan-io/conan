import ast
import os
import shutil

import six

from conans.client.cmd.export_linter import conan_linter
from conans.client.file_copier import FileCopier
from conans.client.output import ScopedOutput
from conans.client.remover import DiskRemover
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.scm import SCM, get_scm_data
from conans.paths import CONANFILE
from conans.search.search import search_recipes, search_packages
from conans.util.files import is_dirty, load, rmdir, save, set_dirty, remove
from conans.util.log import logger


def export_alias(package_layout, target_ref, output, revisions_enabled):
    revision_mode = "hash"
    conanfile = """
from conans import ConanFile

class AliasConanfile(ConanFile):
    alias = "%s"
    revision_mode = "%s"
""" % (target_ref.full_repr(), revision_mode)

    save(package_layout.conanfile(), conanfile)
    digest = FileTreeManifest.create(package_layout.export())
    digest.save(folder=package_layout.export())

    # Create the metadata for the alias
    _update_revision_in_metadata(package_layout=package_layout, revisions_enabled=revisions_enabled,
                                 output=output, path=None, digest=digest,
                                 revision_mode=revision_mode)


def check_casing_conflict(cache, ref):
    # Check for casing conflict
    # Maybe a platform check could be added, but depends on disk partition
    refs = search_recipes(cache, ref, ignorecase=True)
    if refs and ref not in [r.copy_clear_rev() for r in refs]:
        raise ConanException("Cannot export package with same name but different case\n"
                             "You exported '%s' but already existing '%s'"
                             % (str(ref), " ".join(str(s) for s in refs)))


def cmd_export(package_layout, conanfile_path, conanfile, keep_source, revisions_enabled,
               output, hook_manager):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    hook_manager.execute("pre_export", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=package_layout.ref)
    logger.debug("EXPORT: %s" % conanfile_path)

    output.highlight("Exporting package recipe")
    conan_linter(conanfile_path, output)
    output = conanfile.output

    # Get previous digest
    try:
        previous_digest = FileTreeManifest.load(package_layout.export())
    except IOError:
        previous_digest = None
    finally:
        _recreate_folders(package_layout.export(), package_layout.export_sources())

    # Copy sources to target folders
    with package_layout.conanfile_write_lock(output=output):
        origin_folder = os.path.dirname(conanfile_path)
        export_recipe(conanfile, origin_folder, package_layout.export())
        export_source(conanfile, origin_folder, package_layout.export_sources())
        shutil.copy2(conanfile_path, package_layout.conanfile())

        _capture_export_scm_data(conanfile, os.path.dirname(conanfile_path),
                                 package_layout.export(), output,
                                 scm_src_file=package_layout.scm_folder())

        # Execute post-export hook before computing the digest
        hook_manager.execute("post_export", conanfile=conanfile, reference=package_layout.ref,
                             conanfile_path=package_layout.conanfile())

        # Compute the new digest
        digest = FileTreeManifest.create(package_layout.export(), package_layout.export_sources())
        modified_recipe = not previous_digest or previous_digest != digest
        if modified_recipe:
            output.success('A new %s version was exported' % CONANFILE)
            output.info('Folder: %s' % package_layout.export())
        else:
            output.info("The stored package has not changed")
            digest = previous_digest  # Use the old one, keep old timestamp
        digest.save(package_layout.export())

    # Compute the revision for the recipe
    revision = _update_revision_in_metadata(package_layout=package_layout,
                                            revisions_enabled=revisions_enabled,
                                            output=output,
                                            path=os.path.dirname(conanfile_path),
                                            digest=digest,
                                            revision_mode=conanfile.revision_mode)

    # FIXME: Conan 2.0 Clear the registry entry if the recipe has changed
    source_folder = package_layout.source()
    if os.path.exists(source_folder):
        try:
            if is_dirty(source_folder):
                output.info("Source folder is corrupted, forcing removal")
                rmdir(source_folder)
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

    return package_layout.ref.copy_with_rev(revision)


def _capture_export_scm_data(conanfile, conanfile_dir, destination_folder, output, scm_src_file):

    if os.path.exists(scm_src_file):
        os.unlink(scm_src_file)

    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return

    # Resolve SCMData in the user workspace (someone may want to access CVS or import some py)
    scm = SCM(scm_data, conanfile_dir, output)
    captured = scm_data.capture_origin or scm_data.capture_revision

    if scm_data.url == "auto":
        origin = scm.get_qualified_remote_url(remove_credentials=True)
        if not origin:
            raise ConanException("Repo origin cannot be deduced")
        if scm.is_local_repository():
            output.warn("Repo origin looks like a local path: %s" % origin)
        output.success("Repo origin deduced by 'auto': %s" % origin)
        scm_data.url = origin

    if scm_data.revision == "auto":
        if not scm.is_pristine():
            output.warn("Repo status is not pristine: there might be modified files")
        scm_data.revision = scm.get_revision()
        output.success("Revision deduced by 'auto': %s" % scm_data.revision)

    _replace_scm_data_in_conanfile(os.path.join(destination_folder, "conanfile.py"), scm_data)

    if captured:
        # Generate the scm_folder.txt file pointing to the src_path
        src_path = scm.get_local_path_to_url(scm_data.url)
        if src_path:
            save(scm_src_file, os.path.normpath(src_path).replace("\\", "/"))

    return scm_data


def _replace_scm_data_in_conanfile(conanfile_path, scm_data):
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
    for i_body, item in enumerate(tree.body):
        if isinstance(item, ast.ClassDef):
            statements = item.body
            for i, stmt in enumerate(item.body):
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    if isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "scm":
                        try:
                            if i + 1 == len(statements):  # Last statement in my ClassDef
                                if i_body + 1 == len(tree.body):  # Last statement over all
                                    next_line = len(lines)
                                else:
                                    next_line = tree.body[i_body+1].lineno - 1
                            else:
                                next_line = statements[i+1].lineno - 1
                                next_line_content = lines[next_line].strip()
                                if next_line_content.endswith('"""') or next_line_content.endswith("'''"):
                                    next_line += 1
                        except IndexError:
                            next_line = stmt.lineno
                        replace = [line for line in lines[(stmt.lineno-1):next_line]]
                        to_replace.append("".join(replace).lstrip())
                        comments = [line.strip('\n') for line in replace
                                    if line.strip().startswith("#") or not line.strip()]
                        break
    if len(to_replace) != 1:
        raise ConanException("The conanfile.py defines more than one class level 'scm' attribute")

    new_text = "scm = " + ",\n          ".join(str(scm_data).split(",")) + "\n"
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


def _update_revision_in_metadata(package_layout, revisions_enabled, output, path, digest,
                                 revision_mode):
    if revision_mode not in ["scm", "hash"]:
        raise ConanException("Revision mode should be one of 'hash' (default) or 'scm'")

    # Use the proper approach depending on 'revision_mode'
    if revision_mode == "hash":
        revision = digest.summary_hash
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


def _recreate_folders(destination_folder, destination_src_folder):
    try:
        if os.path.exists(destination_folder):
            # Maybe here we want to invalidate cache
            rmdir(destination_folder)
        os.makedirs(destination_folder)
    except Exception as e:
        raise ConanException("Unable to create folder %s\n%s" % (destination_folder, str(e)))

    try:
        if os.path.exists(destination_src_folder):
            rmdir(destination_src_folder)
        os.makedirs(destination_src_folder)
    except Exception as e:
        raise ConanException("Unable to create folder %s\n%s" % (destination_src_folder, str(e)))


def _classify_patterns(patterns):
    patterns = patterns or []
    included, excluded = [], []
    for p in patterns:
        if p.startswith("!"):
            excluded.append(p[1:])
        else:
            included.append(p)
    return included, excluded


def export_source(conanfile, origin_folder, destination_source_folder):
    if isinstance(conanfile.exports_sources, str):
        conanfile.exports_sources = (conanfile.exports_sources, )

    included_sources, excluded_sources = _classify_patterns(conanfile.exports_sources)
    copier = FileCopier([origin_folder], destination_source_folder)
    for pattern in included_sources:
        copier(pattern, links=True, excludes=excluded_sources)
    output = conanfile.output
    package_output = ScopedOutput("%s exports_sources" % output.scope, output)
    copier.report(package_output)


def export_recipe(conanfile, origin_folder, destination_folder):
    if isinstance(conanfile.exports, str):
        conanfile.exports = (conanfile.exports, )

    included_exports, excluded_exports = _classify_patterns(conanfile.exports)

    try:
        os.unlink(os.path.join(origin_folder, CONANFILE + 'c'))
    except OSError:
        pass

    copier = FileCopier([origin_folder], destination_folder)
    for pattern in included_exports:
        copier(pattern, links=True, excludes=excluded_exports)
    output = conanfile.output
    package_output = ScopedOutput("%s exports" % output.scope, output)
    copier.report(package_output)
