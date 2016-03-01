""" ConanFile user tools, as download, etc
"""
import sys
import os
from conans.errors import ConanException
from conans.util.files import _generic_algorithm_sum, save
from patch import fromfile, fromstring
from conans.client.rest.uploader_downloader import Downloader
import requests
from conans.client.output import ConanOutput


def human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
    e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        return "1 byte"

    suffixes_table = [('bytes', 0), ('KB', 0), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(size_bytes)
    for suffix, precision in suffixes_table:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)


def unzip(filename, destination="."):
    if ".tar.gz" in filename or ".tgz" in filename:
        return untargz(filename, destination)
    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))
    with zipfile.ZipFile(filename, "r") as z:
        uncompress_size = sum((file_.file_size for file_ in z.infolist()))
        print "Unzipping %s, this can take a while" % (human_size(uncompress_size))
        extracted_size = 0
        for file_ in z.infolist():
            extracted_size += file_.file_size
            print "Unzipping %.0f %%\r" % (extracted_size * 100.0 / uncompress_size),
            try:
                if len(file_.filename) + len(full_path) > 200:
                    raise ValueError("Filename too long")
                z.extract(file_, full_path)
            except Exception as e:
                print "Error extract %s\n%s" % (file_.filename, str(e))


def untargz(filename, destination="."):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:gz') as tarredgzippedFile:
        tarredgzippedFile.extractall(destination)


def get(url):
    """ high level downloader + unziper + delete temporary zip
    """
    filename = os.path.basename(url)
    download(url, filename)
    unzip(filename)
    os.unlink(filename)


def download(url, filename, verify=True):
    out = ConanOutput(sys.stdout, True)
    if verify:
        # We check the certificate using a list of known verifiers
        import conans.client.rest.cacert as cacert
        verify = cacert.file_path
    downloader = Downloader(requests, out, verify=verify)
    content = downloader.download(url)
    out.writeln("")
    save(filename, content)


def replace_in_file(file_path, search, replace):
    with open(file_path, 'r') as content_file:
        content = content_file.read()
        content = content.replace(search, replace)
    with open(file_path, 'wb') as handle:
        handle.write(content)


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


def patch(base_path=None, patch_file=None, patch_string=None):
    """Applies a diff from file (patch_file)  or string (patch_string)
    in base_path directory or current dir if None"""

    if not patch_file and not patch_string:
        return
    if patch_file:
        patchset = fromfile(patch_file)
    else:
        patchset = fromstring(patch_string)

    patchset.apply(root=base_path)
