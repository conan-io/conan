""" manages the movement of conanfiles and associated files from the user space
to the local store, as an initial step before building or uploading to remotes
"""

import shutil
import os
from conans.util.files import save, load, rmdir, mkdir
from conans.paths import CONAN_MANIFEST, CONANFILE, DIRTY_FILE, EXPORT_SOURCES_DIR
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.client.output import ScopedOutput
from conans.client.file_copier import FileCopier
from conans.model.conan_file import create_exports, create_exports_sources
from conans.client.loader_parse import load_conanfile_class


def load_export_conanfile(conanfile_path, output):
    conanfile = load_conanfile_class(conanfile_path)

    for field in ["url", "license", "description"]:
        field_value = getattr(conanfile, field, None)
        if not field_value:
            output.warn("Conanfile doesn't have '%s'.\n"
                        "It is recommended to add it as attribute" % field)
    if getattr(conanfile, "conan_info", None):
        output.warn("conan_info() method is deprecated, use package_id() instead")

    try:
        # Exports is the only object field, we need to do this, because conan export needs it
        conanfile.exports = create_exports(conanfile)
        conanfile.exports_sources = create_exports_sources(conanfile)
    except Exception as e:  # re-raise with file name
        raise ConanException("%s: %s" % (conanfile_path, str(e)))

    # check name and version were specified

    if not hasattr(conanfile, "name") or not conanfile.name:
        raise ConanException("conanfile didn't specify name")
    if not hasattr(conanfile, "version") or not conanfile.version:
        raise ConanException("conanfile didn't specify version")

    return conanfile


def export_conanfile(output, paths, conanfile, origin_folder, conan_ref, keep_source, filename):
    destination_folder = paths.export(conan_ref)
    previous_digest = _init_export_folder(destination_folder)
    execute_export(conanfile, origin_folder, destination_folder, output, filename)

    digest = FileTreeManifest.create(destination_folder)
    save(os.path.join(destination_folder, CONAN_MANIFEST), str(digest))

    if previous_digest and previous_digest == digest:
        digest = previous_digest
        output.info("The stored package has not changed")
        modified_recipe = False
    else:
        output.success('A new %s version was exported' % CONANFILE)
        output.info('Folder: %s' % destination_folder)
        modified_recipe = True

    source = paths.source(conan_ref, conanfile.short_paths)
    dirty = os.path.join(source, DIRTY_FILE)
    remove = False
    if os.path.exists(dirty):
        output.info("Source folder is dirty, forcing removal")
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
                         "Will be marked as dirty for deletion")
            output.warn(str(e))
            save(os.path.join(source, DIRTY_FILE), "")


def _init_export_folder(destination_folder):
    previous_digest = None
    try:
        if os.path.exists(destination_folder):
            if os.path.exists(os.path.join(destination_folder, CONAN_MANIFEST)):
                manifest_content = load(os.path.join(destination_folder, CONAN_MANIFEST))
                previous_digest = FileTreeManifest.loads(manifest_content)
            # Maybe here we want to invalidate cache
            rmdir(destination_folder)
        os.makedirs(destination_folder)
    except Exception as e:
        raise ConanException("Unable to create folder %s\n%s" % (destination_folder, str(e)))
    return previous_digest


def execute_export(conanfile, origin_folder, destination_folder, output, filename=None):
    def classify(patterns):
        patterns = patterns or []
        included, excluded = [], []
        for p in patterns:
            if p.startswith("!"):
                excluded.append(p[1:])
            else:
                included.append(p)
        return included, excluded

    included_exports, excluded_exports = classify(conanfile.exports)
    included_sources, excluded_sources = classify(conanfile.exports_sources)

    try:
        os.unlink(os.path.join(origin_folder, CONANFILE + 'c'))
    except:
        pass

    copier = FileCopier(origin_folder, destination_folder)
    for pattern in included_exports:
        copier(pattern, links=True, excludes=excluded_exports)
    # create directory for sources, and import them
    export_sources_dir = os.path.join(destination_folder, EXPORT_SOURCES_DIR)
    mkdir(export_sources_dir)
    copier = FileCopier(origin_folder, export_sources_dir)
    for pattern in included_sources:
        copier(pattern, links=True, excludes=excluded_sources)
    package_output = ScopedOutput("%s export" % output.scope, output)
    copier.report(package_output)

    shutil.copy2(os.path.join(origin_folder, filename or CONANFILE),
                 os.path.join(destination_folder, CONANFILE))
