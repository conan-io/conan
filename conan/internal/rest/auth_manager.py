"""
Collaborate with RestApiClient to make remote anonymous and authenticated calls.
Uses user_input to request user's login and password and obtain a token for calling authenticated
methods if receives AuthenticationException from RestApiClient.


Flow:
    Directly invoke a REST method in RestApiClient, example: get_conan.
    if receives AuthenticationException (not open method) will ask user for login and password
    (with LOGIN_RETRIES retries) and retry to call with the new token.
"""

import threading

from conan.api.output import ConanOutput
from conan.internal.rest.remote_credentials import RemoteCredentials
from conan.internal.rest.rest_client import RestApiClient
from conan.internal.errors import AuthenticationException, ForbiddenException
from conan.errors import ConanException

LOGIN_RETRIES = 3


class _RemoteCreds:
    def __init__(self, localdb):
        self._localdb = localdb

    def get(self, remote, msg=True, force_refresh=False):
        """
        Get credentials for a remote.

        Args:
            remote: The remote to get credentials for
            msg: Whether to print connection message
            force_refresh: If True, bypass cache and read from database.
                          Used during double-check to detect if another process updated credentials.
        """
        creds = None if force_refresh else getattr(remote, "_creds", None)
        if creds is None:
            user, token, _ = self._localdb.get_login(remote.url)
            creds = user, token
            if msg:
                usermsg = f"with user '{user}'" if user else "anonymously"
                ConanOutput().info(f"Connecting to remote '{remote.name}' {usermsg}")
            setattr(remote, "_creds", creds)
        return creds

    def set(self, remote, user, token):
        setattr(remote, "_creds", (user, token))
        ConanOutput().success(f"Authenticated in remote '{remote.name}' with user '{user}'")
        self._localdb.store(user, token, None, remote.url)


class ConanApiAuthManager:

    def __init__(self, requester, cache_folder, localdb, global_conf):
        self._requester = requester
        self._creds = _RemoteCreds(localdb)
        self._global_conf = global_conf
        self._cache_folder = cache_folder
        # Thread-level lock for efficient intra-process synchronization
        # This prevents multiple threads from requesting credentials simultaneously
        self._auth_lock = threading.Lock()
        # Process-level lock manager for inter-process synchronization
        # This prevents multiple processes from prompting for credentials simultaneously
        # when running parallel uploads/downloads with expired tokens
        from conan.internal.cache.concurrency_lock import ConcurrencyLock
        self._process_lock_manager = ConcurrencyLock(cache_folder)

    def call_rest_api_method(self, remote, method_name, *args, **kwargs):
        """Handles AuthenticationException and request user to input a user and a password"""
        user, token = self._creds.get(remote, msg=(method_name != "authenticate"))
        rest_client = RestApiClient(remote, token, self._requester, self._global_conf)

        if method_name == "authenticate":
            return self._authenticate(rest_client, remote, *args, **kwargs)

        try:
            ret = getattr(rest_client, method_name)(*args, **kwargs)
            return ret
        except ForbiddenException as e:
            raise ForbiddenException(f"Permission denied for user: '{user}': {e}")
        except AuthenticationException:
            # User valid but not enough permissions
            # token is None when you change user with user command
            # Anonymous is not enough, ask for a user
            ConanOutput().info(f"Remote '{remote.name}' needs authentication, obtaining credentials")

            # Use remote-specific lock to serialize authentication across both threads and processes
            # This prevents multiple threads/processes from prompting for credentials simultaneously
            # Lock ID is based on remote URL to allow concurrent auth to different remotes
            # IMPORTANT: Release lock BEFORE retrying the API call to prevent holding the lock
            # during potentially long operations that might cause token expiry
            import hashlib
            remote_lock_id = f"auth_{hashlib.sha256(remote.url.encode()).hexdigest()[:16]}"

            should_retry = False
            with self._process_lock_manager.lock(
                remote_lock_id,
                wait_msg=f"Waiting for authentication to '{remote.name}' to complete...",
                level=None  # Auth locks don't participate in hierarchy
            ):
                # Also acquire thread lock for efficiency within this process
                with self._auth_lock:
                    # Double-check: another thread/process might have already re-authenticated
                    # while we were waiting for the lock. Force refresh from database to detect
                    # credentials updated by another process (not visible in our cached copy).
                    user_recheck, token_recheck = self._creds.get(remote, msg=False, force_refresh=True)
                    if token_recheck != token:
                        # Token was updated by another thread/process, retry with new token
                        ConanOutput().info(f"Using credentials obtained by another process")
                        should_retry = True
                    else:
                        # We're the first thread/process to authenticate, proceed with getting credentials
                        # But first check: don't retry authentication if we just authenticated with this exact token
                        # This prevents infinite loops when the server rejects a newly-issued token
                        # We use a timestamp to distinguish between:
                        # - Fresh authentication failure (< 0.5 seconds ago): prevent infinite loop
                        # - Old token expiry (>= 0.5 seconds ago): allow re-authentication
                        # Note: 0.5 seconds is short enough to catch immediate rejections but allows
                        #       tokens with very short TTL (e.g., 1.2 seconds in tests) to be refreshed
                        import time
                        last_auth_info = getattr(remote, "_last_authenticated_token", None)
                        if last_auth_info is not None:
                            last_token, last_time = last_auth_info
                            if token is not None and token == last_token and (time.time() - last_time) < 0.5:
                                # Token was just authenticated and immediately failed, prevent infinite loop
                                raise

                        rest_client_recheck = RestApiClient(remote, token_recheck, self._requester,
                                                             self._global_conf)
                        if self._get_credentials_and_authenticate(rest_client_recheck, user_recheck, remote):
                            # Mark this token and timestamp as the last authentication
                            # This is checked above to prevent infinite loops
                            new_token = self._creds.get(remote, msg=False, force_refresh=False)[1]
                            setattr(remote, "_last_authenticated_token", (new_token, time.time()))
                            should_retry = True

            # Retry outside the lock to prevent holding the lock during API calls
            if should_retry:
                return self.call_rest_api_method(remote, method_name, *args, **kwargs)

    def _get_credentials_and_authenticate(self, rest_client, user, remote):
        """Try LOGIN_RETRIES to obtain a password from user input for which
        we can get a valid token from api_client. If a token is returned,
        credentials are stored in localdb and rest method is called"""
        creds = RemoteCredentials(self._cache_folder, self._global_conf)
        for _ in range(LOGIN_RETRIES):
            input_user, input_password, interactive = creds.auth(remote)
            try:
                self._authenticate(rest_client, remote, input_user, input_password)
            except AuthenticationException:
                out = ConanOutput()
                if user is None:
                    out.error('Wrong user or password', error_type="exception")
                else:
                    out.error(f'Wrong password for user "{input_user}"', error_type="exception")
                if not interactive:
                    raise AuthenticationException(f"Authentication error in remote '{remote.name}'")
            else:
                return True
        raise AuthenticationException("Too many failed login attempts, bye!")

    def _authenticate(self, rest_client, remote, user, password):
        try:
            token = rest_client.authenticate(user, password)
        except UnicodeDecodeError:
            raise ConanException("Password contains not allowed symbols")

        # Store result in DB
        self._creds.set(remote, user, token)
