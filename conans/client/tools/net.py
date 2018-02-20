import sys

import os
from conans.client.output import ConanOutput
from conans.client.rest.uploader_downloader import Downloader
from conans.client.tools.files import unzip, check_md5, check_sha1, check_sha256
from conans.errors import ConanException

_global_requester = None


def get(url, md5='', sha1='', sha256='', destination="."):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """
    filename = os.path.basename(url)
    download(url, filename)

    if md5:
        check_md5(filename, md5)
    if sha1:
        check_sha1(filename, sha1)
    if sha256:
        check_sha256(filename, sha256)

    unzip(filename, destination=destination)
    os.unlink(filename)


def ftp_download(ip, filename, login='', password=''):
    import ftplib
    try:
        ftp = ftplib.FTP(ip, login, password)
        ftp.login()
        filepath, filename = os.path.split(filename)
        if filepath:
            ftp.cwd(filepath)
        with open(filename, 'wb') as f:
            ftp.retrbinary('RETR ' + filename, f.write)
    except Exception as e:
        raise ConanException("Error in FTP download from %s\n%s" % (ip, str(e)))
    finally:
        try:
            ftp.quit()
        except:
            pass


def download(url, filename, verify=True, out=None, retry=2, retry_wait=5, overwrite=False,
             auth=None, headers=None):
    out = out or ConanOutput(sys.stdout, True)
    if verify:
        # We check the certificate using a list of known verifiers
        import conans.client.rest.cacert as cacert
        verify = cacert.file_path
    downloader = Downloader(_global_requester, out, verify=verify)
    downloader.download(url, filename, retry=retry, retry_wait=retry_wait, overwrite=overwrite,
                        auth=auth, headers=headers)
    out.writeln("")
