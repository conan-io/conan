import os
import time
import traceback
from collections import namedtuple

from urllib.parse import parse_qs, urljoin, urlparse, urlsplit

from conans.client.downloaders.download import run_downloader
from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.remote_manager import check_compressed_files
from conans.client.rest.client_routes import ClientV1Router
from conans.client.rest.file_uploader import FileUploader
from conans.client.rest.rest_client_common import RestCommonMethods, handle_return_deserializer
from conans.errors import ConanException, NotFoundException, NoRestV2Available, \
    PackageNotFoundException
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, \
    PACKAGE_TGZ_NAME
from conans.util.files import decode_text
from conans.util.log import logger


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
