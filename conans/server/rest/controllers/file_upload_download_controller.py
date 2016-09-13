from conans.server.rest.controllers.controller import Controller
from bottle import request, static_file, FileUpload, cached_property
from conans.server.service.service import FileUploadDownloadService
import os
from unicodedata import normalize
import six
from conans.errors import NotFoundException


class FileUploadDownloadController(Controller):
    """
        Serve requests related with users
    """
    def attach_to(self, app):

        storage_path = app.file_manager.paths.store
        service = FileUploadDownloadService(app.updown_auth_manager, storage_path)

        @app.route(self.route + '/<filepath:path>', method=["GET"])
        def get(filepath):
            token = request.query.get("signature", None)
            file_path = service.get_file_path(filepath, token)
            # https://github.com/kennethreitz/requests/issues/1586
            mimetype = "x-gzip" if filepath.endswith(".tgz") else "auto"
            return static_file(os.path.basename(file_path),
                               root=os.path.dirname(file_path),
                               mimetype=mimetype)

        @app.route(self.route + '/<filepath:path>', method=["PUT"])
        def put(filepath):
            token = request.query.get("signature", None)
            file_saver = ConanFileUpload(request.body, None,
                                         filename=os.path.basename(filepath),
                                         headers=request.headers)
            abs_path = os.path.abspath(os.path.join(storage_path, os.path.normpath(filepath)))
            # Body is a stringIO (generator)
            service.put_file(file_saver, abs_path, token, request.content_length)
            return


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
