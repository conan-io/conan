from conans.model.conan_file import ConanFile
from conans.util.files import load


# complex_search: With ORs and not filtering by not restricted settings
COMPLEX_SEARCH_CAPABILITY = "complex_search"
CHECKSUM_DEPLOY = "checksum_deploy"  # Only when v2
REVISIONS = "revisions"  # Only when enabled in config, not by default look at server_launcher.py
ONLY_V2 = "only_v2"  # Remotes and virtuals from Artifactory returns this capability
MATRIX_PARAMS = "matrix_params"
OAUTH_TOKEN = "oauth_token"
SERVER_CAPABILITIES = [COMPLEX_SEARCH_CAPABILITY, REVISIONS]  # Server is always with revisions
DEFAULT_REVISION_V1 = "0"

__version__ = '2.0.0-alpha1'
