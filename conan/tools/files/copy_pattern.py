import fnmatch
import os
import shutil
from collections import defaultdict

from conans.util.files import mkdir


def copy(conanfile, pattern, src, dst, keep_path=True, excludes=None,
         ignore_case=True):
    """
        It will copy the files matching the pattern from the src folder to the dst, including the
        symlinks to files. If a folder from "src" doesn't contain any file to be copied, it won't be
        created empty at the "dst".
        If in "src" there are symlinks to folders, they will be created at "dst" irrespective if
        they (or the folder where points) have files to be copied or not, unless
        "copy_symlink_folders=False" is specified.

        param pattern: an fnmatch file pattern of the files that should be copied. Eg. *.dll
        param dst: the destination local folder, wrt to current conanfile dir, to which
                   the files will be copied. Eg: "bin"
        param src: the source folder in which those files will be searched. This folder
                   will be stripped from the dst name. Eg.: lib/Debug/x86
        param keep_path: False if you want the relative paths to be maintained from
                         src to dst folders, or just drop. False is useful if you want
                         to collect e.g. many *.libs among many dirs into a single
                         lib dir
        param excludes: Single pattern or a tuple of patterns to be excluded from the copy
        param ignore_case: will do a case-insensitive pattern matching when True

        return: list of copied files
        """
    assert src != dst
    assert not pattern.startswith("..")

    # This is necessary to add the trailing / so it is not reported as symlink
    src = os.path.join(src, "")
    excluded_folder = dst
    files_to_copy, files_symlinked_to_folders = _filter_files(src, pattern, excludes, ignore_case,
                                                           excluded_folder)

    copied_files = _copy_files(files_to_copy, src, dst, keep_path)
    copied_files.extend(_copy_files_symlinked_to_folders(files_symlinked_to_folders, src, dst))

    # FIXME: Not always passed conanfile
    if conanfile:
        _report_files_copied(copied_files, conanfile.output)
    return copied_files


def _filter_files(src, pattern, excludes, ignore_case, excluded_folder):
    """ return a list of the files matching the patterns
    The list will be relative path names wrt to the root src folder
    """
    filenames = []
    files_symlinked_to_folders = []

    if excludes:
        if not isinstance(excludes, (tuple, list)):
            excludes = (excludes, )
        if ignore_case:
            excludes = [e.lower() for e in excludes]
    else:
        excludes = []

    for root, subfolders, files in os.walk(src):
        if root == excluded_folder:
            subfolders[:] = []
            continue

        # Check if any of the subfolders is a symlink
        for subfolder in subfolders:
            relative_path = os.path.relpath(os.path.join(root, subfolder), src)
            if os.path.islink(os.path.join(root, subfolder)):
                if fnmatch.fnmatch(os.path.normpath(relative_path.lower()), pattern):
                    files_symlinked_to_folders.append(relative_path)

        relative_path = os.path.relpath(root, src)
        compare_relative_path = relative_path.lower() if ignore_case else relative_path
        for exclude in excludes:
            if fnmatch.fnmatch(compare_relative_path, exclude):
                subfolders[:] = []
                files = []
                break
        for f in files:
            relative_name = os.path.normpath(os.path.join(relative_path, f))
            filenames.append(relative_name)

    if ignore_case:
        pattern = pattern.lower()
        files_to_copy = [n for n in filenames if fnmatch.fnmatch(os.path.normpath(n.lower()),
                                                                 pattern)]
    else:
        files_to_copy = [n for n in filenames if fnmatch.fnmatchcase(os.path.normpath(n),
                                                                     pattern)]

    for exclude in excludes:
        if ignore_case:
            files_to_copy = [f for f in files_to_copy if not fnmatch.fnmatch(f.lower(), exclude)]
        else:
            files_to_copy = [f for f in files_to_copy if not fnmatch.fnmatchcase(f, exclude)]

    return files_to_copy, files_symlinked_to_folders


def _copy_files(files, src, dst, keep_path):
    """ executes a multiple file copy from [(src_file, dst_file), (..)]
    managing symlinks if necessary
    """
    copied_files = []
    for filename in files:
        abs_src_name = os.path.join(src, filename)
        filename = filename if keep_path else os.path.basename(filename)
        abs_dst_name = os.path.normpath(os.path.join(dst, filename))
        try:
            os.makedirs(os.path.dirname(abs_dst_name))
        except Exception:
            pass
        if os.path.islink(abs_src_name):
            linkto = os.readlink(abs_src_name)  # @UndefinedVariable
            try:
                os.remove(abs_dst_name)
            except OSError:
                pass
            os.symlink(linkto, abs_dst_name)  # @UndefinedVariable
        else:
            shutil.copy2(abs_src_name, abs_dst_name)
        copied_files.append(abs_dst_name)
    return copied_files


def _copy_files_symlinked_to_folders(files_symlinked_to_folders, src, dst):
    """Copy the files that are symlinks to folders from src to dst.
       The files are already filtered with the specified pattern"""
    copied_files = []
    for relative_path in files_symlinked_to_folders:
        abs_path = os.path.join(src, relative_path)
        symlink_path = os.path.join(dst, relative_path)
        # We create the same symlink in dst, no matter if it is absolute or relative
        link_dst = os.readlink(abs_path)  # This could be perfectly broken

        # Create the parent directory that will contain the symlink file
        mkdir(os.path.dirname(symlink_path))
        # If the symlink is already there, remove it (multiple copy(*.h) copy(*.dll))
        if os.path.islink(symlink_path):
            os.unlink(symlink_path)
        os.symlink(link_dst, symlink_path)
        copied_files.append(symlink_path)
    return copied_files


def _report_files_copied(copied, scoped_output, message_suffix="Copied"):
    ext_files = defaultdict(list)
    for f in copied:
        _, ext = os.path.splitext(f)
        ext_files[ext].append(os.path.basename(f))

    if not ext_files:
        return False

    for ext, files in ext_files.items():
        files_str = (": " + ", ".join(files)) if len(files) < 5 else ""
        file_or_files = "file" if len(files) == 1 else "files"
        if not ext:
            scoped_output.info("%s %d %s%s" % (message_suffix, len(files), file_or_files, files_str))
        else:
            scoped_output.info("%s %d '%s' %s%s"
                               % (message_suffix, len(files), ext, file_or_files, files_str))
    return True
