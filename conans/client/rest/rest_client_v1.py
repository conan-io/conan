import os
import time
import traceback
from collections import namedtuple

from urllib.parse import urljoin, urlparse

from conans.client.rest.client_routes import ClientV1Router
from conans.client.rest.rest_client_common import RestCommonMethods


def complete_url(base_url, url):
    """ Ensures that an url is absolute by completing relative urls with
        the remote url. urls that are already absolute are not modified.
    """
    if bool(urlparse(url).netloc):
        return url
    return urljoin(base_url, url)


class RestV1Methods(RestCommonMethods):

    @property
    def router(self):
        return ClientV1Router(self.remote_url.rstrip("/"), self._artifacts_properties,
                              self._matrix_params)
