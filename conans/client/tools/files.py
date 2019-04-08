import logging
import os
import platform
import sys
from contextlib import contextmanager
from fnmatch import fnmatch

import six
from patch import fromfile, fromstring

from conans.client.output import ConanOutput
from conans.errors import ConanException
from conans.unicode import get_cwd
from conans.util.fallbacks import default_output
from conans.util.files import (_generic_algorithm_sum, load, save)

UNIT_SIZE = 1000.0


@contextmanager
def chdir(newdir):
    old_path = get_cwd()
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


def unzip(filename, destination=".", keep_permissions=False, pattern=None, output=None):
    """
    Unzip a zipped file
    :param filename: Path to the zip file
    :param destination: Destination folder
    :param keep_permissions: Keep the zip permissions. WARNING: Can be
    dangerous if the zip was not created in a NIX system, the bits could
    produce undefined permission schema. Use this option only if you are sure
    that the zip was created correctly.
    :param pattern: Extract only paths matching the pattern. This should be a
    Unix shell-style wildcard, see fnmatch documentation for more details.
    :param output: output
    :return:
    """
    output = default_output(output, 'conans.client.tools.files.unzip')

    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination, pattern)
    if filename.endswith(".tar.xz") or filename.endswith(".txz"):
        if six.PY2:
            raise ConanException("XZ format not supported in Python 2. Use Python 3 instead")
        return untargz(filename, destination, pattern)

    import zipfile
    full_path = os.path.normpath(os.path.join(get_cwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(the_size, uncomp_size):
            the_size = (the_size * 100.0 / uncomp_size) if uncomp_size != 0 else 0
            txt_msg = "Unzipping %d %%"
            if the_size > print_progress.last_size + 1:
                output.rewrite_line(txt_msg % the_size)
                print_progress.last_size = the_size
                if int(the_size) == 99:
                    output.rewrite_line(txt_msg % 100)
                    output.writeln("")
    else:
        def print_progress(_, __):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        if not pattern:
            zip_info = z.infolist()
        else:
            zip_info = [zi for zi in z.infolist() if fnmatch(zi.filename, pattern)]
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


def untargz(filename, destination=".", pattern=None):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:*') as tarredgzippedFile:
        if not pattern:
            tarredgzippedFile.extractall(destination)
        else:
            members = list(filter(lambda m: fnmatch(m.name, pattern),
                                  tarredgzippedFile.getmembers()))
            tarredgzippedFile.extractall(destination, members=members)


def check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature:
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


def patch(base_path=None, patch_file=None, patch_string=None, strip=0, output=None):
    """Applies a diff from file (patch_file)  or string (patch_string)
    in base_path directory or current dir if None"""

    class PatchLogHandler(logging.Handler):
        def __init__(self):
            logging.Handler.__init__(self, logging.DEBUG)
            self.output = output or ConanOutput(sys.stdout, True)
            self.patchname = patch_file if patch_file else "patch"

        def emit(self, record):
            logstr = self.format(record)
            if record.levelno == logging.WARN:
                self.output.warn("%s: %s" % (self.patchname, logstr))
            else:
                self.output.info("%s: %s" % (self.patchname, logstr))

    patchlog = logging.getLogger("patch")
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

    def decode_clean(path, prefix):
        path = path.decode("utf-8").replace("\\", "/")
        if path.startswith(prefix):
            path = path[2:]
        return path

    def strip_path(path):
        tokens = path.split("/")[strip:]
        path = "/".join(tokens)
        if base_path:
            path = os.path.join(base_path, path)
        return path
    # account for new and deleted files, upstream dep won't fix them
    items = []
    for p in patchset:
        source = decode_clean(p.source, "a/")
        target = decode_clean(p.target, "b/")
        if "dev/null" in source:
            target = strip_path(target)
            hunks = [s.decode("utf-8") for s in p.hunks[0].text]
            new_file = "".join(hunk[1:] for hunk in hunks)
            save(target, new_file)
        elif "dev/null" in target:
            source = strip_path(source)
            os.unlink(source)
        else:
            items.append(p)
    patchset.items = items

    if not patchset.apply(root=base_path, strip=strip):
        raise ConanException("Failed to apply patch: %s" % patch_file)


def _manage_text_not_found(search, file_path, strict, function_name, output):
    message = "%s didn't find pattern '%s' in '%s' file." % (function_name, search, file_path)
    if strict:
        raise ConanException(message)
    else:
        output.warn(message)
        return False


def replace_in_file(file_path, search, replace, strict=True, output=None):
    output = default_output(output, 'conans.client.tools.files.replace_in_file')

    content = load(file_path)
    if -1 == content.find(search):
        _manage_text_not_found(search, file_path, strict, "replace_in_file", output=output)
    content = content.replace(search, replace)
    content = content.encode("utf-8")
    with open(file_path, "wb") as handle:
        handle.write(content)


def replace_path_in_file(file_path, search, replace, strict=True, windows_paths=None, output=None):
    output = default_output(output, 'conans.client.tools.files.replace_path_in_file')

    if windows_paths is False or (windows_paths is None and platform.system() != "Windows"):
        return replace_in_file(file_path, search, replace, strict=strict, output=output)

    def normalized_text(text):
        return text.replace("\\", "/").lower()

    content = load(file_path)
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

    content = content.encode("utf-8")
    with open(file_path, "wb") as handle:
        handle.write(content)

    return True


def replace_prefix_in_pc_file(pc_file, new_prefix):
    content = load(pc_file)
    lines = []
    for line in content.splitlines():
        if line.startswith("prefix="):
            lines.append('prefix=%s' % new_prefix)
        else:
            lines.append(line)
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
    result = []
    for lib_folder in lib_folders:
        if not os.path.exists(lib_folder):
            conanfile.output.warn("Lib folder doesn't exist, can't collect libraries: "
                                  "{0}".format(lib_folder))
            continue
        files = os.listdir(lib_folder)
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in (".so", ".lib", ".a", ".dylib"):
                if ext != ".lib" and name.startswith("lib"):
                    name = name[3:]
                if name in result:
                    conanfile.output.warn("Library '%s' was either already found in a previous "
                                          "'conanfile.cpp_info.libdirs' folder or appears several "
                                          "times with a different file extension" % name)
                else:
                    result.append(name)
    result.sort()
    return result


def which(filename):
    """ same affect as posix which command or shutil.which from python3 """
    def verify(filepath):
        if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
            return os.path.join(path, filename)
        return None

    def _get_possible_filenames(filename):
        extensions_win = (os.getenv("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
                          if "." not in filename else [])
        extensions = [".sh"] if platform.system() != "Windows" else extensions_win
        extensions.insert(1, "")  # No extension
        return ["%s%s" % (filename, entry.lower()) for entry in extensions]

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
