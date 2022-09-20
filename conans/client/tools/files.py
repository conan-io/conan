import gzip
import logging
import os
import platform
import stat
import subprocess
import sys
from contextlib import contextmanager
from fnmatch import fnmatch

import six
from patch_ng import fromfile, fromstring

from conans.client.output import ConanOutput
from conans.errors import ConanException
from conans.util.fallbacks import default_output
from conans.util.files import (_generic_algorithm_sum, load, save)

UNIT_SIZE = 1000.0
# Library extensions supported by collect_libs
VALID_LIB_EXTENSIONS = (".so", ".lib", ".a", ".dylib", ".bc")


@contextmanager
def chdir(newdir):
    old_path = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(old_path)


def human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. B, KB, MB, GB, TB, PB
    Note that bytes will be reported in whole numbers but KB and above will have
    greater precision.  e.g. 43 B, 443 KB, 4.3 MB, 4.43 GB, etc
    """

    suffixes_table = [('B', 0), ('KB', 1), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(size_bytes)
    for suffix, precision in suffixes_table:
        if num < UNIT_SIZE:
            break
        num /= UNIT_SIZE

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s%s" % (formatted_size, suffix)


def unzip(filename, destination=".", keep_permissions=False, pattern=None, output=None,
          strip_root=False):
    """
    Unzip a zipped file
    :param filename: Path to the zip file
    :param destination: Destination folder (or file for .gz files)
    :param keep_permissions: Keep the zip permissions. WARNING: Can be
    dangerous if the zip was not created in a NIX system, the bits could
    produce undefined permission schema. Use this option only if you are sure
    that the zip was created correctly.
    :param pattern: Extract only paths matching the pattern. This should be a
    Unix shell-style wildcard, see fnmatch documentation for more details.
    :param output: output
    :param flat: If all the contents are in a single dir, flat that directory.
    :return:
    """
    output = default_output(output, 'conans.client.tools.files.unzip')

    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination, pattern, strip_root)
    if filename.endswith(".gz"):
        with gzip.open(filename, 'rb') as f:
            file_content = f.read()
        target_name = filename[:-3] if destination == "." else destination
        save(target_name, file_content)
        return
    if filename.endswith(".tar.xz") or filename.endswith(".txz"):
        if six.PY2:
            raise ConanException("XZ format not supported in Python 2. Use Python 3 instead")
        return untargz(filename, destination, pattern, strip_root)

    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(the_size, uncomp_size):
            the_size = (the_size * 100.0 / uncomp_size) if uncomp_size != 0 else 0
            txt_msg = "Unzipping %d %%"
            if the_size > print_progress.last_size + 1:
                output.rewrite_line(txt_msg % the_size)
                print_progress.last_size = the_size
                if int(the_size) == 99:
                    output.rewrite_line(txt_msg % 100)
    else:
        def print_progress(_, __):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        zip_info = z.infolist()
        if pattern:
            zip_info = [zi for zi in zip_info if fnmatch(zi.filename, pattern)]
        if strip_root:
            names = [n.replace("\\", "/") for n in z.namelist()]
            common_folder = os.path.commonprefix(names).split("/", 1)[0]
            if not common_folder and len(names) > 1:
                raise ConanException("The zip file contains more than 1 folder in the root")
            if len(names) == 1 and len(names[0].split("/", 1)) == 1:
                raise ConanException("The zip file contains a file in the root")
            # Remove the directory entry if present
            # Note: The "zip" format contains the "/" at the end if it is a directory
            zip_info = [m for m in zip_info if m.filename != (common_folder + "/")]
            for member in zip_info:
                name = member.filename.replace("\\", "/")
                member.filename = name.split("/", 1)[1]

        uncompress_size = sum((file_.file_size for file_ in zip_info))
        if uncompress_size > 100000:
            output.info("Unzipping %s, this can take a while" % human_size(uncompress_size))
        else:
            output.info("Unzipping %s" % human_size(uncompress_size))
        extracted_size = 0

        print_progress.last_size = -1
        if platform.system() == "Windows":
            for file_ in zip_info:
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                except Exception as e:
                    output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        else:  # duplicated for, to avoid a platform check for each zipped file
            for file_ in zip_info:
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                    if keep_permissions:
                        # Could be dangerous if the ZIP has been created in a non nix system
                        # https://bugs.python.org/issue15795
                        perm = file_.external_attr >> 16 & 0xFFF
                        os.chmod(os.path.join(full_path, file_.filename), perm)
                except Exception as e:
                    output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        output.writeln("")


def untargz(filename, destination=".", pattern=None, strip_root=False):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:*') as tarredgzippedFile:
        if not pattern and not strip_root:
            tarredgzippedFile.extractall(destination)
        else:
            members = tarredgzippedFile.getmembers()

            if strip_root:
                names = [n.replace("\\", "/") for n in tarredgzippedFile.getnames()]
                common_folder = os.path.commonprefix(names).split("/", 1)[0]
                if not common_folder and len(names) > 1:
                    raise ConanException("The tgz file contains more than 1 folder in the root")
                if len(names) == 1 and len(names[0].split("/", 1)) == 1:
                    raise ConanException("The tgz file contains a file in the root")
                # Remove the directory entry if present
                members = [m for m in members if m.name != common_folder]
                for member in members:
                    name = member.name.replace("\\", "/")
                    member.name = name.split("/", 1)[1]
                    member.path = member.name
                    if member.linkpath.startswith(common_folder):
                        # https://github.com/conan-io/conan/issues/11065
                        linkpath = member.linkpath.replace("\\", "/")
                        member.linkpath = linkpath.split("/", 1)[1]
                        member.linkname = member.linkpath
            if pattern:
                members = list(filter(lambda m: fnmatch(m.name, pattern),
                                      tarredgzippedFile.getmembers()))
            tarredgzippedFile.extractall(destination, members=members)


def check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature.lower():
        raise ConanException("%s signature failed for '%s' file. \n"
                             " Provided signature: %s  \n"
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
                                                          signature,
                                                          real_signature))


def check_sha1(file_path, signature):
    check_with_algorithm_sum("sha1", file_path, signature)


def check_md5(file_path, signature):
    check_with_algorithm_sum("md5", file_path, signature)


def check_sha256(file_path, signature):
    check_with_algorithm_sum("sha256", file_path, signature)


def patch(base_path=None, patch_file=None, patch_string=None, strip=0, output=None, fuzz=False):
    """ Applies a diff from file (patch_file)  or string (patch_string)
        in base_path directory or current dir if None
    :param base_path: Base path where the patch should be applied.
    :param patch_file: Patch file that should be applied.
    :param patch_string: Patch string that should be applied.
    :param strip: Number of folders to be stripped from the path.
    :param output: Stream object.
    :param fuzz: Should accept fuzzy patches.
    """

    class PatchLogHandler(logging.Handler):
        def __init__(self):
            logging.Handler.__init__(self, logging.DEBUG)
            self.output = output or ConanOutput(sys.stdout, sys.stderr, color=True)
            self.patchname = patch_file if patch_file else "patch_ng"

        def emit(self, record):
            logstr = self.format(record)
            if record.levelno == logging.WARN:
                self.output.warn("%s: %s" % (self.patchname, logstr))
            else:
                self.output.info("%s: %s" % (self.patchname, logstr))

    patchlog = logging.getLogger("patch_ng")
    if patchlog:
        patchlog.handlers = []
        patchlog.addHandler(PatchLogHandler())

    if not patch_file and not patch_string:
        return
    if patch_file:
        patchset = fromfile(patch_file)
    else:
        patchset = fromstring(patch_string.encode())

    if not patchset:
        raise ConanException("Failed to parse patch: %s" % (patch_file if patch_file else "string"))

    if not patchset.apply(root=base_path, strip=strip, fuzz=fuzz):
        raise ConanException("Failed to apply patch: %s" % patch_file)


def _manage_text_not_found(search, file_path, strict, function_name, output):
    message = "%s didn't find pattern '%s' in '%s' file." % (function_name, search, file_path)
    if strict:
        raise ConanException(message)
    else:
        output.warn(message)
        return False


@contextmanager
def _add_write_permissions(file_path):
    # Assumes the file already exist in disk
    write = stat.S_IWRITE
    saved_permissions = os.stat(file_path).st_mode
    if saved_permissions & write == write:
        yield
        return
    try:
        os.chmod(file_path, saved_permissions | write)
        yield
    finally:
        os.chmod(file_path, saved_permissions)


def replace_in_file(file_path, search, replace, strict=True, output=None, encoding=None):
    output = default_output(output, 'conans.client.tools.files.replace_in_file')

    encoding_in = encoding or "auto"
    encoding_out = encoding or "utf-8"
    content = load(file_path, encoding=encoding_in)
    if -1 == content.find(search):
        _manage_text_not_found(search, file_path, strict, "replace_in_file", output=output)
    content = content.replace(search, replace)
    content = content.encode(encoding_out)
    with _add_write_permissions(file_path):
        save(file_path, content, only_if_modified=False, encoding=encoding_out)


def replace_path_in_file(file_path, search, replace, strict=True, windows_paths=None, output=None,
                         encoding=None):
    output = default_output(output, 'conans.client.tools.files.replace_path_in_file')

    if windows_paths is False or (windows_paths is None and platform.system() != "Windows"):
        return replace_in_file(file_path, search, replace, strict=strict, output=output,
                               encoding=encoding)

    def normalized_text(text):
        return text.replace("\\", "/").lower()

    encoding_in = encoding or "auto"
    encoding_out = encoding or "utf-8"
    content = load(file_path, encoding=encoding_in)
    normalized_content = normalized_text(content)
    normalized_search = normalized_text(search)
    index = normalized_content.find(normalized_search)
    if index == -1:
        return _manage_text_not_found(search, file_path, strict, "replace_path_in_file",
                                      output=output)

    while index != -1:
        content = content[:index] + replace + content[index + len(search):]
        normalized_content = normalized_text(content)
        index = normalized_content.find(normalized_search)

    content = content.encode(encoding_out)
    with _add_write_permissions(file_path):
        save(file_path, content, only_if_modified=False, encoding=encoding_out)

    return True


def replace_prefix_in_pc_file(pc_file, new_prefix):
    content = load(pc_file)
    lines = []
    for line in content.splitlines():
        if line.startswith("prefix="):
            lines.append('prefix=%s' % new_prefix)
        else:
            lines.append(line)
    with _add_write_permissions(pc_file):
        save(pc_file, "\n".join(lines))


def _path_equals(path1, path2):
    path1 = os.path.normpath(path1)
    path2 = os.path.normpath(path2)
    if platform.system() == "Windows":
        path1 = path1.lower().replace("sysnative", "system32")
        path2 = path2.lower().replace("sysnative", "system32")
    return path1 == path2


def collect_libs(conanfile, folder=None):
    if not conanfile.package_folder:
        return []
    if folder:
        lib_folders = [os.path.join(conanfile.package_folder, folder)]
    else:
        lib_folders = [os.path.join(conanfile.package_folder, folder)
                       for folder in conanfile.cpp_info.libdirs]

    ref_libs = {}
    for lib_folder in lib_folders:
        if not os.path.exists(lib_folder):
            conanfile.output.warn("Lib folder doesn't exist, can't collect libraries: "
                                  "{0}".format(lib_folder))
            continue
        # In case of symlinks, only keep shortest file name in the same "group"
        files = os.listdir(lib_folder)
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in VALID_LIB_EXTENSIONS:
                real_lib = os.path.basename(os.path.realpath(os.path.join(lib_folder, f)))
                if real_lib not in ref_libs or len(f) < len(ref_libs[real_lib]):
                    ref_libs[real_lib] = f

    result = []
    for f in ref_libs.values():
        name, ext = os.path.splitext(f)
        if ext != ".lib" and name.startswith("lib"):
            name = name[3:]
        if name not in result:
            result.append(name)
    result.sort()
    return result


def which(filename):
    """ same affect as posix which command or shutil.which from python3 """
    # FIXME: Replace with shutil.which in Conan 2.0
    def verify(file_abspath):
        return os.path.isfile(file_abspath) and os.access(file_abspath, os.X_OK)

    def _get_possible_filenames(fname):
        if platform.system() != "Windows":
            extensions = [".sh", ""]
        else:
            if "." in filename:  # File comes with extension already
                extensions = [""]
            else:
                pathext = os.getenv("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
                extensions = [extension.lower() for extension in pathext]
                extensions.insert(1, "")  # No extension
        return ["%s%s" % (fname, extension) for extension in extensions]

    possible_names = _get_possible_filenames(filename)
    for path in os.environ["PATH"].split(os.pathsep):
        for name in possible_names:
            filepath = os.path.abspath(os.path.join(path, name))
            if verify(filepath):
                return filepath
            if platform.system() == "Windows":
                filepath = filepath.lower()
                if "system32" in filepath:
                    # python return False for os.path.exists of exes in System32 but with SysNative
                    trick_path = filepath.replace("system32", "sysnative")
                    if verify(trick_path):
                        return trick_path

    return None


def _replace_with_separator(filepath, sep):
    tmp = load(filepath)
    ret = sep.join(tmp.splitlines())
    if tmp.endswith("\n"):
        ret += sep
    save(filepath, ret)


def unix2dos(filepath):
    _replace_with_separator(filepath, "\r\n")


def dos2unix(filepath):
    _replace_with_separator(filepath, "\n")


def rename(src, dst):
    # FIXME: Deprecated, use new interface from conan.tools
    """
    rename a file or folder to avoid "Access is denied" error on Windows
    :param src: Source file or folder
    :param dst: Destination file or folder
    """
    if os.path.exists(dst):
        raise ConanException("rename {} to {} failed, dst exists.".format(src, dst))

    if platform.system() == "Windows" and which("robocopy") and os.path.isdir(src):
        # /move Moves files and directories, and deletes them from the source after they are copied.
        # /e Copies subdirectories. Note that this option includes empty directories.
        # /ndl Specifies that directory names are not to be logged.
        # /nfl Specifies that file names are not to be logged.
        process = subprocess.Popen(["robocopy", "/move", "/e", "/ndl", "/nfl", src, dst],
                                   stdout=subprocess.PIPE)
        process.communicate()
        if process.returncode > 7:  # https://ss64.com/nt/robocopy-exit.html
            raise ConanException("rename {} to {} failed.".format(src, dst))
    else:
        try:
            os.rename(src, dst)
        except Exception as err:
            raise ConanException("rename {} to {} failed: {}".format(src, dst, err))


def remove_files_by_mask(directory, pattern):
    removed_names = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if fnmatch(filename, pattern):
                fullname = os.path.join(root, filename)
                os.unlink(fullname)
                removed_names.append(os.path.relpath(fullname, directory))
    return removed_names


def fix_symlinks(conanfile, raise_if_error=False):
    """ Fix the symlinks in the conanfile.package_folder: make symlinks relative and remove
        those links to files outside the package (it will print an error, or raise
        if 'raise_if_error' evaluates to true).
    """
    offending_files = []

    def work_on_element(dirpath, element, token):
        fullpath = os.path.join(dirpath, element)
        if not os.path.islink(fullpath):
            return

        link_target = os.readlink(fullpath)
        if link_target in ['/dev/null', ]:
            return

        link_abs_target = os.path.join(dirpath, link_target)
        link_rel_target = os.path.relpath(link_abs_target, conanfile.package_folder)
        if link_rel_target.startswith('..') or os.path.isabs(link_rel_target):
            offending_file = os.path.relpath(fullpath, conanfile.package_folder)
            offending_files.append(offending_file)
            conanfile.output.error("{token} '{item}' links to a {token} outside the package, "
                                   "it's been removed.".format(item=offending_file, token=token))
            os.unlink(fullpath)
        elif not os.path.exists(link_abs_target):
            # This is a broken symlink. Failure is controlled by config variable
            #  'general.skip_broken_symlinks_check'. Do not fail here.
            offending_file = os.path.relpath(fullpath, conanfile.package_folder)
            offending_files.append(offending_file)
            conanfile.output.error("{token} '{item}' links to a path that doesn't exist, it's"
                                   " been removed.".format(item=offending_file, token=token))
            os.unlink(fullpath)
        elif link_target != link_rel_target:
            os.unlink(fullpath)
            os.symlink(link_rel_target, fullpath)

    for (dirpath, dirnames, filenames) in os.walk(conanfile.package_folder):
        for filename in filenames:
            work_on_element(dirpath, filename, token="file")

        for dirname in dirnames:
            work_on_element(dirpath, dirname, token="directory")

    if offending_files and raise_if_error:
        raise ConanException("There are invalid symlinks in the package!")
