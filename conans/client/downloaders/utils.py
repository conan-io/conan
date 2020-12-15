from six.moves.urllib_parse import urlsplit, urlunsplit

from conans.util.sha import sha256 as sha256_sum


def hash_url(url, checksum, user_download):
    """ For Api V2, the cached downloads always have recipe and package REVISIONS in the URL,
    making them immutable, and perfect for cached downloads of artifacts. For V2 checksum
    will always be None.
    For ApiV1, the checksum is obtained from the server via "get_snapshot()" methods, but
    the URL in the apiV1 contains the signature=xxx for signed urls, but that can change,
    so better strip it from the URL before the hash
    """
    scheme, netloc, path, _, _ = urlsplit(url)
    # append empty query and fragment before unsplit
    if not user_download:  # removes ?signature=xxx
        url = urlunsplit((scheme, netloc, path, "", ""))
    if checksum is not None:
        url += checksum
    h = sha256_sum(url.encode())
    return h
