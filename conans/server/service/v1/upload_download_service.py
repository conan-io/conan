import os

import jwt

from conans.errors import NotFoundException, RequestErrorException
from conans.util.log import logger
from conans.util.files import mkdir


class FileUploadDownloadService(object):
    """Handles authorization from token and upload and download files"""

    def __init__(self, updown_auth_manager, base_store_folder):
        self.updown_auth_manager = updown_auth_manager
        self.base_store_folder = base_store_folder

    def get_file_path(self, filepath, token):
        try:
            encoded_path, _, user = self.updown_auth_manager.get_resource_info(token)
            if not self._valid_path(filepath, encoded_path):
                logger.info("Invalid path file!! %s: %s" % (user, filepath))
                raise NotFoundException("File not found")
            logger.debug("Get file: user=%s path=%s" % (user, filepath))
            file_path = os.path.normpath(os.path.join(self.base_store_folder, encoded_path))
            return file_path
        except (jwt.ExpiredSignatureError, jwt.DecodeError, AttributeError):
            raise NotFoundException("File not found")

    def put_file(self, file_saver, abs_filepath, token, upload_size):
        """
        file_saver is an object with the save() method without parameters
        """
        try:
            encoded_path, filesize, user = self.updown_auth_manager.get_resource_info(token)
            # Check size
            if upload_size != filesize:
                logger.debug("Invalid size file!!: %s: %s" % (user, abs_filepath))
                raise RequestErrorException("Bad file size")

            abs_encoded_path = os.path.abspath(os.path.join(self.base_store_folder, encoded_path))
            if not self._valid_path(abs_filepath, abs_encoded_path):
                raise NotFoundException("File not found")
            logger.debug("Put file: %s: %s" % (user, abs_filepath))
            mkdir(os.path.dirname(abs_filepath))
            if os.path.exists(abs_filepath):
                os.remove(abs_filepath)
            file_saver.save(os.path.dirname(abs_filepath))

        except (jwt.ExpiredSignatureError, jwt.DecodeError, AttributeError):
            raise NotFoundException("File not found")

    def _valid_path(self, filepath, encoded_path):
        if encoded_path == filepath:
            path = os.path.join(self.base_store_folder, encoded_path)
            path = os.path.normpath(path)
            # Protect from path outside storage "../.."
            if not path.startswith(self.base_store_folder):
                return False
            return True
        else:
            return False
