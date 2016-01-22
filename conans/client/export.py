""" manages the movement of conanfiles and associated files from the user space
to the local store, as an initial step before building or uploading to remotes
"""

import shutil
import os
from conans.util.files import save, load, rmdir
from conans.paths import CONAN_MANIFEST, CONANFILE
from conans.errors import ConanException
from conans.client.file_copier import FileCopier
from conans.model.manifest import FileTreeManifest


def export_conanfile(output, paths, file_patterns, origin_folder, conan_ref):
    destination_folder = paths.export(conan_ref)

    previous_digest = _init_export_folder(destination_folder)

    _export(file_patterns, origin_folder, destination_folder)

    digest = FileTreeManifest.create(destination_folder)

    if previous_digest and previous_digest.file_sums == digest.file_sums:
        digest = previous_digest
    else:
        output.success('A new %s version was exported' % CONANFILE)

    save(os.path.join(destination_folder, CONAN_MANIFEST), str(digest))
    output.success('%s exported to local storage' % CONANFILE)
    output.success('Folder: %s' % destination_folder)


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


def _export(file_patterns, origin_folder, destination_folder):
    file_patterns = file_patterns or []
    try:
        os.unlink(os.path.join(origin_folder, CONANFILE + 'c'))
    except:
        pass

    copier = FileCopier(origin_folder, destination_folder)
    for pattern in file_patterns:
        copier(pattern)

    shutil.copy2(os.path.join(origin_folder, CONANFILE), destination_folder)
