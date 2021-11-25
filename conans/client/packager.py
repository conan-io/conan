from conans.client.file_copier import report_copied_files
from conans.paths import CONANINFO


def report_files_from_manifest(scoped_output, manifest):
    copied_files = list(manifest.files())
    copied_files.remove(CONANINFO)

    if not copied_files:
        scoped_output.warning("No files in this package!")
        return

    report_copied_files(copied_files, scoped_output, message_suffix="Packaged")
