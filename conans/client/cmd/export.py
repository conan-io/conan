import ast
import os
import shutil
import six

from conans.client.cmd.export_linter import conan_linter
from conans.client.file_copier import FileCopier
from conans.client.output import ScopedOutput
from conans.client.source import get_scm_data
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.scm import SCM
from conans.paths import CONAN_MANIFEST, CONANFILE
from conans.util.files import save, rmdir, is_dirty, set_dirty, mkdir, load
from conans.util.log import logger
from conans.search.search import search_recipes


def export_alias(reference, target_reference, client_cache):
    if reference.name != target_reference.name:
        raise ConanException("An alias can only be defined to a package with the same name")
    conanfile = """
from conans import ConanFile

class AliasConanfile(ConanFile):
    alias = "%s"
""" % str(target_reference)

    export_path = client_cache.export(reference)
    mkdir(export_path)
    save(os.path.join(export_path, CONANFILE), conanfile)
    mkdir(client_cache.export_sources(reference))
    digest = FileTreeManifest.create(export_path)
    digest.save(export_path)


def cmd_export(conanfile_path, conanfile, reference, keep_source, output, client_cache,
               plugin_manager):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    plugin_manager.execute("pre_export", conanfile=conanfile, conanfile_path=conanfile_path,
                           reference=reference)
    logger.debug("Exporting %s" % conanfile_path)
    output.highlight("Exporting package recipe")

    conan_linter(conanfile_path, output)
    # Maybe a platform check could be added, but depends on disk partition
    conan_ref_str = str(reference)
    refs = search_recipes(client_cache, conan_ref_str, ignorecase=True)
    if refs and reference not in refs:
        raise ConanException("Cannot export package with same name but different case\n"
                             "You exported '%s' but already existing '%s'"
                             % (conan_ref_str, " ".join(str(s) for s in refs)))

    with client_cache.conanfile_write_lock(reference):
        _export_conanfile(conanfile_path, conanfile.output, client_cache, conanfile, reference,
                          keep_source)
    conanfile_cache_path = client_cache.conanfile(reference)
    plugin_manager.execute("post_export", conanfile=conanfile, conanfile_path=conanfile_cache_path,
                           reference=reference)


def _capture_export_scm_data(conanfile, conanfile_dir, destination_folder, output, paths, conan_ref):

    scm_src_file = paths.scm_folder(conan_ref)
    if os.path.exists(scm_src_file):
        os.unlink(scm_src_file)

    scm_data = get_scm_data(conanfile)

    if not scm_data or not (scm_data.capture_origin or scm_data.capture_revision):
        return

    scm = SCM(scm_data, conanfile_dir)

    if scm_data.url == "auto":
        origin = scm.get_qualified_remote_url()
        if not origin:
            raise ConanException("Repo origin cannot be deduced by 'auto'")
        if scm.is_local_repository():
            output.warn("Repo origin looks like a local path: %s" % origin)
        output.success("Repo origin deduced by 'auto': %s" % origin)
        scm_data.url = origin
    if scm_data.revision == "auto":
        if not scm.is_pristine():
            output.warn("Repo status is not pristine: there might be modified files")
        scm_data.revision = scm.get_revision()
        output.success("Revision deduced by 'auto': %s" % scm_data.revision)

    # Generate the scm_folder.txt file pointing to the src_path
    src_path = scm.get_repo_root()
    save(scm_src_file, src_path.replace("\\", "/"))
    _replace_scm_data_in_conanfile(os.path.join(destination_folder, "conanfile.py"),
                                   scm_data)


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
                        except IndexError:
                            next_line = stmt.lineno
                        replace = [line for line in lines[(stmt.lineno-1):next_line]
                                   if line.strip()]
                        to_replace.append("".join(replace).lstrip())
                        break
    if len(to_replace) != 1:
        raise ConanException("The conanfile.py defines more than one class level 'scm' attribute")

    new_text = "scm = " + ",\n          ".join(str(scm_data).split(",")) + "\n"
    content = content.replace(to_replace[0], new_text)
    content = content if not headers else ''.join(headers) + content
    save(conanfile_path, content)


def _export_conanfile(conanfile_path, output, paths, conanfile, conan_ref, keep_source):

    exports_folder = paths.export(conan_ref)
    exports_source_folder = paths.export_sources(conan_ref, conanfile.short_paths)
    previous_digest = _init_export_folder(exports_folder, exports_source_folder)
    _execute_export(conanfile_path, conanfile, exports_folder, exports_source_folder, output)
    shutil.copy2(conanfile_path, os.path.join(exports_folder, CONANFILE))

    _capture_export_scm_data(conanfile, os.path.dirname(conanfile_path), exports_folder,
                             output, paths, conan_ref)

    digest = FileTreeManifest.create(exports_folder, exports_source_folder)

    if previous_digest and previous_digest == digest:
        output.info("The stored package has not changed")
        modified_recipe = False
        digest = previous_digest  # Use the old one, keep old timestamp
    else:
        output.success('A new %s version was exported' % CONANFILE)
        output.info('Folder: %s' % exports_folder)
        modified_recipe = True
    digest.save(exports_folder)

    source = paths.source(conan_ref, conanfile.short_paths)
    remove = False
    if is_dirty(source):
        output.info("Source folder is corrupted, forcing removal")
        remove = True
    elif modified_recipe and not keep_source and os.path.exists(source):
        output.info("Package recipe modified in export, forcing source folder removal")
        output.info("Use the --keep-source, -k option to skip it")
        remove = True
    if remove:
        output.info("Removing 'source' folder, this can take a while for big packages")
        try:
            # remove only the internal
            rmdir(source)
        except BaseException as e:
            output.error("Unable to delete source folder. "
                         "Will be marked as corrupted for deletion")
            output.warn(str(e))
            set_dirty(source)


def _init_export_folder(destination_folder, destination_src_folder):
    previous_digest = None
    try:
        if os.path.exists(destination_folder):
            if os.path.exists(os.path.join(destination_folder, CONAN_MANIFEST)):
                previous_digest = FileTreeManifest.load(destination_folder)
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
    return previous_digest


def _execute_export(conanfile_path, conanfile, destination_folder, destination_source_folder,
                    output):

    if isinstance(conanfile.exports, str):
        conanfile.exports = (conanfile.exports, )
    if isinstance(conanfile.exports_sources, str):
        conanfile.exports_sources = (conanfile.exports_sources, )

    origin_folder = os.path.dirname(conanfile_path)

    def classify_patterns(patterns):
        patterns = patterns or []
        included, excluded = [], []
        for p in patterns:
            if p.startswith("!"):
                excluded.append(p[1:])
            else:
                included.append(p)
        return included, excluded

    included_exports, excluded_exports = classify_patterns(conanfile.exports)
    included_sources, excluded_sources = classify_patterns(conanfile.exports_sources)

    try:
        os.unlink(os.path.join(origin_folder, CONANFILE + 'c'))
    except OSError:
        pass

    copier = FileCopier(origin_folder, destination_folder)
    for pattern in included_exports:
        copier(pattern, links=True, excludes=excluded_exports)
    copier = FileCopier(origin_folder, destination_source_folder)
    for pattern in included_sources:
        copier(pattern, links=True, excludes=excluded_sources)
    package_output = ScopedOutput("%s export" % output.scope, output)
    copier.report(package_output)
