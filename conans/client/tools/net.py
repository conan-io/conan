import os

from conans.client.rest.uploader_downloader import Downloader
from conans.client.tools.files import check_md5, check_sha1, check_sha256, unzip
from conans.errors import ConanException
from conans.util.fallbacks import default_output, default_requester


def get(url, md5='', sha1='', sha256='', destination=".", filename="", keep_permissions=False,
        pattern=None, requester=None, output=None, verify=True, retry=None, retry_wait=None,
        overwrite=False, auth=None, headers=None):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """
    if not filename and ("?" in url or "=" in url):
        raise ConanException("Cannot deduce file name form url. Use 'filename' parameter.")

    filename = filename or os.path.basename(url)
    download(url, filename, out=output, requester=requester, verify=verify, retry=retry,
             retry_wait=retry_wait, overwrite=overwrite, auth=auth, headers=headers)

    if md5:
        check_md5(filename, md5)
    if sha1:
        check_sha1(filename, sha1)
    if sha256:
        check_sha256(filename, sha256)

    unzip(filename, destination=destination, keep_permissions=keep_permissions, pattern=pattern,
          output=output)
    os.unlink(filename)


def ftp_download(ip, filename, login='', password=''):
    import ftplib
    try:
        ftp = ftplib.FTP(ip)
        ftp.login(login, password)
        filepath, filename = os.path.split(filename)
        if filepath:
            ftp.cwd(filepath)
        with open(filename, 'wb') as f:
            ftp.retrbinary('RETR ' + filename, f.write)
    except Exception as e:
        try:
            os.unlink(filename)
        except OSError:
            pass
        raise ConanException("Error in FTP download from %s\n%s" % (ip, str(e)))
    finally:
        try:
            ftp.quit()
        except:
            pass


def download(url, filename, verify=True, out=None, retry=None, retry_wait=None, overwrite=False,
             auth=None, headers=None, requester=None):

    if retry is None:
        retry = 2
    if retry_wait is None:
        retry_wait = 5

    out = default_output(out, 'conans.client.tools.net.download')
    requester = default_requester(requester, 'conans.client.tools.net.download')

    downloader = Downloader(requester=requester, output=out, verify=verify)
    downloader.download(url, filename, retry=retry, retry_wait=retry_wait, overwrite=overwrite,
                        auth=auth, headers=headers)
    out.writeln("")
