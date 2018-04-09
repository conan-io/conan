import tempfile
import platform
from conans.errors import ConanException
import os

_global_output = None


def _get_gpg():
    import gnupg
    try:
        _GPG_HOME_DIR = tempfile.mkdtemp(suffix="_conan_gpg")
        gpgbinary = "gpg.exe" if platform.system() == "Windows" else "gpg"
        return gnupg.GPG(gpgbinary=gpgbinary, gnupghome=_GPG_HOME_DIR)
    except OSError as err:
        raise ConanException("pygnupg was unable to find GPG binary. Reported error was: %s"
                             % err.args[0])


def _get_keys(gpg, pubkey, keyserver):
    if os.path.isfile(pubkey):
        # import pubkey from a file
        with open(pubkey, "r") as f:
            import_key_result = gpg.import_keys(f.read())
    elif len(pubkey) == 8 or len(pubkey) == 40:
        # this is a fingerprint or keyid
        keyserver = "keys.gnupg.net" if keyserver is None else keyserver
        import_key_result = gpg.recv_keys(keyserver, pubkey)
    else:
        # this is a GPG public key ascii-armored in a string
        import_key_result = gpg.import_keys(pubkey)

    # check if key was imported correctly
    try:
        # This was failing because results was empty (in windows). It might depend on the gpg version
        if "problem" in import_key_result.results[0]:
            raise ConanException("failed to import public key from file: %s "
                                 % import_key_result.problem_reason[import_key_result.results[0]["problem"]])

        fingerprint = import_key_result.fingerprints[0]
        return fingerprint
    except Exception as e:
        raise ConanException("failed to import public key from file: %s " % str(e))


def _verify(gpg, sig_file, data_file):
    if sig_file is None:
        with open(data_file, "rb") as f:
            verify_result = gpg.verify_file(f)
    else:
        with open(sig_file, "rb") as f:
            verify_result = gpg.verify_file(f, data_file)
    return verify_result


def verify_gpg_sig(data_file, pubkey, sig_file=None, delete_after=True,
                   keyserver=None):
    """ verify a supplied GPG signature for a file.

        data_file: filename of the data to verify, e.g. "awesome-lib-v1.tar.gz"

        pubkey: either a filename or key fingerprint / keyid of the public key
        e.g. "developer_pubkey.txt" or "0B8DA90F"

        sig_file: file name of detached signature, e.g.
        "awesome-lib-v1.tar.gz.sig" or "awesome-lib-v1.tar.gz.asc"
        if not provided, assume a signature is present in the file itself

        keyserver: address of the keyserver to retrieve public key from.
        keys.gnupg.net is used if none is given
    """

    gpg = _get_gpg()
    fingerprint = _get_keys(gpg, pubkey, keyserver)

    try:
        verify_result = _verify(gpg, sig_file, data_file)
    finally:
        if delete_after:
            delete_result = gpg.delete_keys(fingerprint)
            if delete_result.status != 'ok':
                _global_output.warn("couldn't cleanup GPG keyring")

    if not verify_result.valid:
        raise ConanException("""GPG signature verification failed for file: %s
                                using pubkey with fingerprint : %s.
                                status message is: %s
                                """
                             % (data_file, fingerprint, verify_result.status))
