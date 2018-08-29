import os
import shutil

from conans.client.cmd.export_linter import conan_linter
from conans.client.file_copier import FileCopier
from conans.client.output import ScopedOutput
from conans.client.source import get_scm_data
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.scm import SCM
from conans.paths import CONAN_MANIFEST, CONANFILE
from conans.util.files import save, rmdir, is_dirty, set_dirty, mkdir
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


def cmd_export(conanfile_path, conanfile, reference, keep_source, output, client_cache):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    logger.debug("Exporting %s" % conanfile_path)
    output.highlight("Exporting package recipe")

    conan_linter(conanfile_path, output)
    for field in ["url", "license", "description"]:
        field_value = getattr(conanfile, field, None)
        if not field_value:
            output.warn("Conanfile doesn't have '%s'.\n"
                        "It is recommended to add it as attribute" % field)

    conan_ref_str = str(reference)
    # Maybe a platform check could be added, but depends on disk partition
    refs = search_recipes(client_cache, conan_ref_str, ignorecase=True)
    if refs and reference not in refs:
        raise ConanException("Cannot export package with same name but different case\n"
                             "You exported '%s' but already existing '%s'"
                             % (conan_ref_str, " ".join(str(s) for s in refs)))

    with client_cache.conanfile_write_lock(reference):
        _export_conanfile(conanfile_path, conanfile.output, client_cache, conanfile, reference,
                          keep_source)


def _capture_export_scm_data(conanfile, src_path, destination_folder, output, paths, conan_ref):

    scm_src_file = paths.scm_folder(conan_ref)
    if os.path.exists(scm_src_file):
        os.unlink(scm_src_file)

    scm_data = get_scm_data(conanfile)

    if not scm_data or not (scm_data.capture_origin or scm_data.capture_revision):
        return

    scm = SCM(scm_data, src_path)

    if scm_data.url == "auto":
        origin = scm.get_remote_url()
        if not origin:
            raise ConanException("Repo origin cannot be deduced by 'auto'")
        if os.path.exists(origin):
            output.warn("Repo origin looks like a local path: %s" % origin)
            origin = origin.replace("\\", "/")
        output.success("Repo origin deduced by 'auto': %s" % origin)
        scm_data.url = origin
    if scm_data.revision == "auto":
        scm_data.revision = scm.get_revision()
        output.success("Revision deduced by 'auto': %s" % scm_data.revision)

    # Generate the scm_folder.txt file pointing to the src_path
    save(scm_src_file, src_path.replace("\\", "/"))
    scm_data.replace_in_file(os.path.join(destination_folder, "conanfile.py"))


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
