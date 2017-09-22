import sys

import os
from conans.client.output import ConanOutput
from conans.client.rest.uploader_downloader import Downloader
from conans.client.tools.files import unzip
from conans.errors import ConanException

_global_requester = None


def get(url):
    """ high level downloader + unziper + delete temporary zip
    """
    filename = os.path.basename(url)
    download(url, filename)
    unzip(filename)
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


def download(url, filename, verify=True, out=None, retry=2, retry_wait=5):
    out = out or ConanOutput(sys.stdout, True)
    if verify:
        # We check the certificate using a list of known verifiers
        import conans.client.rest.cacert as cacert
        verify = cacert.file_path
    downloader = Downloader(_global_requester, out, verify=verify)
    downloader.download(url, filename, retry=retry, retry_wait=retry_wait)
    out.writeln("")
