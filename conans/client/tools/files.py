import platform
from contextlib import contextmanager

import logging

import re

import os
import sys

from conans.client.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import load, save, _generic_algorithm_sum
from patch import fromfile, fromstring


_global_output = None


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
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s%s" % (formatted_size, suffix)


def unzip(filename, destination=".", keep_permissions=False):
    """
    Unzip a zipped file
    :param filename: Path to the zip file
    :param destination: Destination folder
    :param keep_permissions: Keep the zip permissions. WARNING: Can be dangerous if the zip was not created in a NIX
    system, the bits could produce undefined permission schema. Use only this option if you are sure that the
    zip was created correctly.
    :return:
    """
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination)
    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(the_size, uncomp_size):
            the_size = (the_size * 100.0 / uncomp_size) if uncomp_size != 0 else 0
            txt_msg = "Unzipping %.0f %%" % the_size
            _global_output.rewrite_line(txt_msg)
    else:
        def print_progress(_, __):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        uncompress_size = sum((file_.file_size for file_ in z.infolist()))
        if uncompress_size > 100000:
            _global_output.info("Unzipping %s, this can take a while" % human_size(uncompress_size))
        else:
            _global_output.info("Unzipping %s" % human_size(uncompress_size))
        extracted_size = 0
        if platform.system() == "Windows":
            for file_ in z.infolist():
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    # Win path limit is 260 chars
                    if len(file_.filename) + len(full_path) >= 260:
                        raise ValueError("Filename too long")
                    z.extract(file_, full_path)
                except Exception as e:
                    _global_output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        else:  # duplicated for, to avoid a platform check for each zipped file
            for file_ in z.infolist():
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
                    _global_output.error("Error extract %s\n%s" % (file_.filename, str(e)))


def untargz(filename, destination="."):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:*') as tarredgzippedFile:
        tarredgzippedFile.extractall(destination)


def check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature:
        raise ConanException("%s signature failed for '%s' file."
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
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

    if not patchset.apply(root=base_path, strip=strip):
        raise ConanException("Failed to apply patch: %s" % patch_file)


def replace_in_file(file_path, search, replace, strict=True):
    content = load(file_path)
    if -1 == content.find(search):
        message = "replace_in_file didn't find pattern '%s' in '%s' file." % (search, file_path)
        if strict:
            raise ConanException(message)
        else:
            _global_output.warn(message)
    content = content.replace(search, replace)
    content = content.encode("utf-8")
    with open(file_path, "wb") as handle:
        handle.write(content)


def replace_prefix_in_pc_file(pc_file, new_prefix):
    content = load(pc_file)
    lines = []
    for line in content.splitlines():
        if line.startswith("prefix="):
            lines.append('prefix=%s' % new_prefix)
        else:
            lines.append(line)
    save(pc_file, "\n".join(lines))


def unix_path(path):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file"""
    pattern = re.compile(r'([a-z]):\\', re.IGNORECASE)
    return pattern.sub('/\\1/', path).replace('\\', '/').lower()


def collect_libs(conanfile, folder="lib"):
    if not conanfile.package_folder:
        return []
    lib_folder = os.path.join(conanfile.package_folder, folder)
    if not os.path.exists(lib_folder):
        conanfile.output.warn("Lib folder doesn't exist, can't collect libraries")
        return []
    files = os.listdir(lib_folder)
    result = []
    for f in files:
        name, ext = os.path.splitext(f)
        if ext in (".so", ".lib", ".a", ".dylib"):
            if ext != ".lib" and name.startswith("lib"):
                name = name[3:]
            result.append(name)
    return result