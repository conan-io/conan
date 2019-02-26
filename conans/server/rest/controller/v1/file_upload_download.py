import os
from unicodedata import normalize

import six
from bottle import FileUpload, cached_property, request, static_file

from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.service.mime import get_mime_type
from conans.server.service.v1.upload_download_service import FileUploadDownloadService


class FileUploadDownloadController(object):
    """
        Serve requests related with users
    """
    @staticmethod
    def attach_to(app):
        r = BottleRoutes()
        storage_path = app.server_store.store
        service = FileUploadDownloadService(app.updown_auth_manager, storage_path)

        @app.route(r.v1_updown_file, method=["GET"])
        def get(the_path):
            token = request.query.get("signature", None)
            file_path = service.get_file_path(the_path, token)
            # https://github.com/kennethreitz/requests/issues/1586
            return static_file(os.path.basename(file_path),
                               root=os.path.dirname(file_path),
                               mimetype=get_mime_type(file_path))

        @app.route(r.v1_updown_file, method=["PUT"])
        def put(the_path):
            token = request.query.get("signature", None)
            file_saver = ConanFileUpload(request.body, None,
                                         filename=os.path.basename(the_path),
                                         headers=request.headers)
            abs_path = os.path.abspath(os.path.join(storage_path, os.path.normpath(the_path)))
            # Body is a stringIO (generator)
            service.put_file(file_saver, abs_path, token, request.content_length)


class ConanFileUpload(FileUpload):
    """Code copied from bottle but removing filename normalizing
    FIXME: Review bottle.FileUpload and analyze possible security or general issues    """
    @cached_property
    def filename(self):
        ''' Name of the file on the client file system, but normalized to ensure
            file system compatibility. An empty filename is returned as 'empty'.

            Only ASCII letters, digits, dashes, underscores and dots are
            allowed in the final filename. Accents are removed, if possible.
            Whitespace is replaced by a single dash. Leading or tailing dots
            or dashes are removed. The filename is limited to 255 characters.
        '''
        fname = self.raw_filename
        if six.PY2:
            if not isinstance(fname, unicode):
                fname = fname.decode('utf8', 'ignore')
        fname = normalize('NFKD', fname).encode('ASCII', 'ignore').decode('ASCII')
        fname = os.path.basename(fname.replace('\\', os.path.sep))
#         fname = re.sub(r'[^a-zA-Z0-9-_.\s]', '', fname).strip()
#         fname = re.sub(r'[-\s]+', '-', fname).strip('.-')
        return fname[:255] or 'empty'
