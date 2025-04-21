import argparse
from pathlib import Path
import pathlib
import tempfile

from conan.api.conan_api import ConanAPI
from conan.api.output import Color, ConanOutput
from conan.errors import ConanException

import os
import re
from io import BytesIO
import sys

from conan import conan_version
from conan.internal.conan_app import ConanApp
from conan.internal.model.version import Version
from conan.internal.model.profile import Profile
from conan.internal.runner.output import RunnerOutput


class SSHRunner:
    def __init__(
        self,
        conan_api: ConanAPI,
        command: str,
        host_profile: Profile,
        build_profile: Profile,
        args: argparse.Namespace,
        raw_args: list[str],
    ):
        self.conan_api = conan_api
        self.command = command
        self.host_profile = host_profile
        self.build_profile = build_profile
        self.args = args
        self.raw_args = raw_args

        try:
            hostname = self._create_ssh_connection()
        except Exception as e:
            raise ConanException(f"Error creating SSH connection: {e}")
        self.output = ConanOutput()
        self.output.set_warnings_as_errors(True)
        self.runner_output = RunnerOutput(hostname)
        self.output.status(f"Connected to {hostname}", fg=Color.BRIGHT_MAGENTA)
        self.remote_conn = RemoteConnection(self.client, self.runner_output)

    def run(self):
        self._ensure_runner_environment()
        self._copy_profiles()
        self._copy_working_conanfile_path()
        self._remote_create()

    def _create_ssh_connection(self) -> str:
        try:
            from paramiko.config import SSHConfig
            from paramiko.client import SSHClient, AutoAddPolicy
        except ImportError:
            raise ConanException("Paramiko is required for SSH runner, try installing it with 'pip install paramiko'")

        hostname = self.host_profile.runner.get("host")
        if not hostname:
            raise ConanException("Host not specified in runner.ssh configuration")
        configfile = self.host_profile.runner.get("configfile", False)
        if configfile and configfile not in ["False", "false", "0"]:
            if configfile in ["True", "true", "1"]:
                ssh_config_file = Path.home() / ".ssh" / "config"
            else:
                ssh_config_file = Path(configfile)
            if not ssh_config_file.exists():
                raise ConanException(f"SSH config file not found at {ssh_config_file}")
            ssh_config = SSHConfig.from_file(open(ssh_config_file))
            if ssh_config and ssh_config.lookup(hostname):
                hostname = ssh_config.lookup(hostname)['hostname']
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(AutoAddPolicy())  # Auto accept unknown keys
        self.client.load_system_host_keys()
        self.client.connect(hostname)
        return hostname

    def _ensure_runner_environment(self):
        # Check python3 is available in remote host
        if self.remote_conn.run_command("python3 --version", "Checking python3 version").success:
            self.remote_python_command = "python3"
        else:
            result = self.remote_conn.run_command("python --version", "Checking python version")
            if result.success and "Python 3" in result.stdout:
                self.remote_python_command = "python"
            else:
                self.output.error("Unable to locate Python 3 executable in remote SSH environment")

        # Determine if remote host is Windows
        result = self.remote_conn.run_command(f'{self.remote_python_command} -c "import os; print(os.name)"', "Checking remote OS type")
        if not result.success:
            self.output.error("Unable to determine remote OS type")
        self.is_remote_windows = result.stdout == "nt"

        # Get remote user home folder
        result = self.remote_conn.run_command(f'{self.remote_python_command} -c "from pathlib import Path; print(Path.home())"', "Checking remote home folder")
        if not result.success:
            self.output.error("Unable to determine remote home user folder")
        home_folder = result.stdout

        # Expected remote paths
        remote_folder = Path(home_folder) / ".conan2remote"
        remote_folder = remote_folder.as_posix().replace("\\", "/")
        self.remote_workspace = remote_folder
        remote_conan_home = Path(home_folder) / ".conan2remote" / "conanhome"
        remote_conan_home = remote_conan_home.as_posix().replace("\\", "/")
        self.remote_conan_home = remote_conan_home

        # Ensure remote folders exist
        for folder in [remote_folder, remote_conan_home]:
            if not self.remote_conn.run_command(f'{self.remote_python_command} -c "import os; os.makedirs(\'{folder}\', exist_ok=True)"', f"Checking {folder} folder exists").success:
                self.output.error(f"Unable to create remote workfolder at {folder}: {result.stderr}")

        # TODO: allow multiple venv given the client side conan version
        requested_conan_version = "dev" if conan_version.pre == "dev" else str(conan_version)

        conan_venv = remote_folder + "/venv"
        if self.is_remote_windows:
            conan_cmd = remote_folder + "/venv/Scripts/conan.exe"
        else:
            conan_cmd = remote_folder + "/venv/bin/conan"

        # Check if remote Conan executable exists, otherwise invoke pip inside venv
        has_remote_conan = self.remote_conn.check_file_exists(conan_cmd)

        if self.is_remote_windows:
            python_command = remote_folder + "/venv" + "/Scripts" + "/python.exe"
        else:
            python_command = remote_folder + "/venv" + "/bin" + "/python"

        if not has_remote_conan:
            self.output.verbose(f"Creating remote venv")
            result = self.remote_conn.run_command(f"{self.remote_python_command} -m venv {conan_venv}", "Creating remote venv")
            if not result.success:
                self.output.error(f"Unable to create remote venv: {result.stderr}")
            self._install_conan_remotely(python_command, requested_conan_version)
        else:
            version = self.remote_conn.run_command(f"{conan_cmd} --version", "Checking conan version", verbose=True).stdout
            remote_conan_version = Version(version[version.rfind(" ")+1:])
            if requested_conan_version == "dev" and remote_conan_version.bump(1) == str(conan_version).replace("-dev", ""):
                pass
            elif remote_conan_version != requested_conan_version:
                self.output.verbose(f"Remote Conan version mismatch: {remote_conan_version} != {requested_conan_version}")
                self._install_conan_remotely(python_command, requested_conan_version)

        if not self.remote_conn.run_command(f"{conan_cmd} remote update conancenter --url='https://center2.conan.io'", "Updating conancenter remote").success:
            self.output.error(f"Unable to update conancenter remote: {result.stderr}")

        self._create_remote_conan_wrapper(remote_conan_home, remote_folder, conan_cmd)

    def _install_conan_remotely(self, python_command: str, version: str):
        self.output.verbose(f"Installing conan version: {version}")
        # Note: this may fail on windows
        result = self.remote_conn.run_command(f"{python_command} -m pip install conan{f'=={version}' if version != 'dev' else ' --upgrade'}", "Installing conan")
        if not result.success:
            self.output.error(f"Unable to install conan in venv: {result.stderr}")

    def _create_remote_conan_wrapper(self, remote_conan_home: str, remote_folder: str, conan_cmd: str):

        # Create conan wrapper with proper environment variables
        remote_env = {
            'CONAN_HOME': remote_conan_home,
            'CONAN_RUNNER_ENVIRONMENT': "1" # This env will prevent conan (running remotely) to start an infinite remote call
        }
        if self.is_remote_windows:
            # Wrapper script with environment variables preset
            env_lines = "\n".join([f"set {k}={v}" for k,v in remote_env.items()])
            conan_wrapper_contents = f"""@echo off\n{env_lines}\n{conan_cmd} %*\n"""
        else:
            env_lines = "\n".join([f"export {k}={v}" for k,v in remote_env.items()])
            conan_wrapper_contents = f"""{env_lines}\n{conan_cmd} $@\n"""

        self.remote_conan = self.remote_conn.create_remote_script(conan_wrapper_contents, remote_folder + "/conan", self.is_remote_windows)
        self.remote_conn.run_command(f"{self.remote_conan} config home", "Checking conan home", verbose=True)
        if not self.remote_conn.run_command(f"{self.remote_conan} profile detect --force", "Detecting remote profile").success:
            self.output.error("Error creating default profile in remote machine")

    def _copy_profiles(self):
        self.output.status("Copying profiles and recipe to host...", fg=Color.BRIGHT_MAGENTA)
        if not self.remote_conan_home:
            raise ConanException("Remote Conan home folder not set")
        remote_profile_path = Path(self.remote_conan_home) / "profiles"
        # If profile path does not exist, create the folder to avoid errors
        if not self.remote_conn.check_file_exists(remote_profile_path.as_posix()):
            self.remote_conn.mkdir(remote_profile_path.as_posix())
        # Iterate over all profiles and copy using sftp
        for profile in set(self.args.profile_host + (self.args.profile_build or [])):
            dest_filename = remote_profile_path / profile
            profile_path = self.conan_api.profiles.get_path(profile)
            self.output.verbose(f"Copying profile '{profile}': {profile_path} -> {dest_filename}")
            self.remote_conn.put(profile_path, dest_filename.as_posix())
        if not self.args.profile_build:
            dest_filename = remote_profile_path / "default" # in remote use "default" profile
            default_build_profile = self.conan_api.profiles.get_default_build()
            self.output.verbose(f"Copying default profile: {default_build_profile} -> {dest_filename}")
            self.remote_conn.put(default_build_profile, dest_filename.as_posix())

    def _copy_working_conanfile_path(self):
        resolved_path = Path(self.args.path).resolve()
        if resolved_path.is_file():
            resolved_path = resolved_path.parent

        if not resolved_path.is_dir():
            return ConanException("Error determining conanfile directory")

        # Create temporary destination directory
        temp_dir_create_cmd = f"""{self.remote_python_command} -c "import tempfile; print(tempfile.mkdtemp(dir='{self.remote_workspace}'))" """
        result = self.remote_conn.run_command(temp_dir_create_cmd, "Creating remote temporary directory")
        if not result.success or not result.stdout:
            self.output.error(f"Unable to create remote temporary directory: {result.stderr}")
        self.remote_create_dir = result.stdout.replace("\\", '/')
        _Path = pathlib.PureWindowsPath if self.is_remote_windows else pathlib.PurePath

        # Base case: Conanfile located at the root of the project
        remote_tmp_dir = _Path(self.remote_create_dir)

        # Check if recipe defines a root folder
        app = ConanApp(self.conan_api)
        remotes = self.conan_api.remotes.list(self.args.remote) if not self.args.no_remote else []
        conanfile = app.loader.load_consumer(resolved_path / "conanfile.py", remotes=remotes)
        if hasattr(conanfile, "layout"):
            try:
                conanfile.layout()
                if conanfile.folders.root:
                    root_relative_path = Path(conanfile.folders.root)
                    tmp = (resolved_path / root_relative_path).resolve()
                    extra_path = resolved_path.relative_to(tmp)
                    self.remote_create_dir = (remote_tmp_dir / extra_path).as_posix()
                    resolved_path = tmp
            except Exception:
                pass
        # Copy current folder to destination using sftp
        for root, dirs, files in os.walk(resolved_path.as_posix()):
            relative_root = Path(root).relative_to(resolved_path)
            dirs[:] = [d for d in dirs if d not in {'venv', '.venv'}] # Filter out virtualenv folders
            for dir in dirs:
                dst = remote_tmp_dir.joinpath(relative_root).joinpath(dir).as_posix()
                self.remote_conn.mkdir(dst)
            for file in files:
                orig = os.path.join(root, file)
                dst = remote_tmp_dir.joinpath(relative_root).joinpath(file).as_posix()
                self.remote_conn.put(orig, dst)

    def _remote_create(self):
        raw_args = self.raw_args
        raw_args[raw_args.index(self.args.path)] = self.remote_create_dir
        raw_args = " ".join(raw_args)
        raw_args = raw_args.replace("&", '"&"').replace("*", '"*"')

        _Path = pathlib.PureWindowsPath if self.is_remote_windows else pathlib.PurePath
        remote_json_output = _Path(self.remote_create_dir).joinpath("conan_create.json").as_posix()
        conan_create_cmd = f'{self.remote_conan} create {raw_args} --format json > {remote_json_output}'
        script_path = _Path(self.remote_create_dir).joinpath("conan_create").as_posix()
        script_path = self.remote_conn.create_remote_script(conan_create_cmd, script_path, self.is_remote_windows)

        if self.remote_conn.run_interactive_command(script_path, self.is_remote_windows, f"Running conan create {raw_args}"):
            self._update_local_cache(remote_json_output)

        self.client.close()

    def _update_local_cache(self, json_result: str):
        _Path = pathlib.PureWindowsPath if self.is_remote_windows else pathlib.PurePath
        pkg_list_json = _Path(self.remote_create_dir).joinpath("pkg_list.json").as_posix()
        # List every package (built or cached) because local cache could have been deleted
        pkg_list_command = f"{self.remote_conan} list --graph={json_result} --format=json > {pkg_list_json}"
        _, stdout, _ = self.client.exec_command(pkg_list_command)
        if stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to generate remote package list")

        conan_cache_tgz = _Path(self.remote_create_dir).joinpath("cache.tgz").as_posix()
        self.output.status("Retrieving remote artifacts into local cache...", fg=Color.BRIGHT_MAGENTA)
        self.output.verbose("Remote cache tgz: " + conan_cache_tgz)
        cache_save_command = f"{self.remote_conan} cache save --list {pkg_list_json} --file {conan_cache_tgz}"
        _, stdout, _ = self.client.exec_command(cache_save_command)
        if stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to save remote conan cache state")

        with tempfile.TemporaryDirectory() as tmp:
            local_cache_tgz = os.path.join(tmp, 'cache.tgz')
            self.remote_conn.get(conan_cache_tgz, local_cache_tgz)
            self.output.verbose("Retrieved local cache: " + local_cache_tgz)
            self.conan_api.cache.restore(local_cache_tgz)


class RemoteConnection:
    def __init__(self, client, runner_output: RunnerOutput):
        from paramiko.client import SSHClient
        self.client: SSHClient = client
        self.runner_output = runner_output

    def put(self, src: str, dst: str) -> None:
        try:
            sftp = self.client.open_sftp()
            sftp.put(src, dst)
            sftp.close()
        except IOError as e:
            self.runner_output.error(f"Unable to copy {src} to {dst}:\n{e}")

    def get(self, src: str, dst: str) -> None:
        try:
            sftp = self.client.open_sftp()
            sftp.get(src, dst)
            sftp.close()
        except IOError as e:
            self.runner_output.error(f"Unable to copy from remote {src} to {dst}:\n{e}")

    def mkdir(self, folder: str) -> None:
        sftp = self.client.open_sftp()
        sftp.mkdir(folder)
        sftp.close()

    def check_file_exists(self, file: str) -> bool:
        try:
            sftp = self.client.open_sftp()
            sftp.stat(file)
            sftp.close()
            return True
        except FileNotFoundError:
            return False

    def create_remote_script(self, script: str, script_path: str, is_remote_windows: bool) -> str:
        script_path += ".bat" if is_remote_windows else ".sh"
        try:
            sftp = self.client.open_sftp()
            sftp.putfo(BytesIO(script.encode()), script_path)
            sftp.chmod(script_path, 0o755)
            sftp.close()
        except Exception as e:
            self.runner_output.error(f"Unable to create remote script in {script_path}:\n{e}")
        return script_path

    class RunResult:
        def __init__(self, success, stdout, stderr):
            self.success = success
            self.stdout = stdout
            self.stderr = stderr

    def run_command(self, command: str, friendly_command: str = "", verbose: bool = False) -> RunResult:
        _, stdout, stderr = self.client.exec_command(command)
        log = self.runner_output.status if verbose else self.runner_output.verbose
        log(f'{friendly_command}...', fg=Color.BLUE)
        self.runner_output.debug(f'$ {command}')
        result = RemoteConnection.RunResult(stdout.channel.recv_exit_status() == 0,
                                            stdout.read().decode().strip(),
                                            stderr.read().decode().strip())
        log(f"{result.stdout}")
        return result

    def run_interactive_command(self, command: str, is_remote_windows: bool, friendly_command: str = "") -> bool:
        ''' Run a command in an SSH session.
            When requesting a pseudo-terminal from the server,
            ensure we pass width and height that matches the current
            terminal
            :return: True if the command succeeded
        '''
        self.runner_output.status(f'{friendly_command}...', fg=Color.BLUE)
        self.runner_output.debug(f"$ {command}")
        channel = self.client.get_transport().open_session()
        if sys.stdout.isatty():
            width, height = os.get_terminal_size()
        else:
            width, height = 80, 24
        width -= self.runner_output.padding
        channel.get_pty(width=width, height=height)

        channel.exec_command(command)
        stdout = channel.makefile("r")
        first_line = True

        cursor_movement_pattern = re.compile(r'(\x1b\[(\d+);(\d+)H)')

        def remove_cursor_movements(data):
            """Replace cursor movements with newline if column is 1, or empty otherwise."""
            def replace_cursor_match(match):
                column = int(match.group(3))
                if column == 1:
                    return "\n"  # Replace with newline if column is 1
                return ""        # Otherwise, replace with empty string
            return cursor_movement_pattern.sub(replace_cursor_match, data)

        while not stdout.channel.exit_status_ready():
            line = stdout.channel.recv(2048)
            if first_line and is_remote_windows:
                # Avoid clearing and moving the cursor when the remote server is Windows
                # https://github.com/PowerShell/Win32-OpenSSH/issues/1738#issuecomment-789434169
                line = line.replace(b"\x1b[2J\x1b[m\x1b[H", b"").replace(b"\r\n", b"")
                first_line = False
            # This is the easiest and better working approach but not testable
            # sys.stdout.buffer.write(line)
            # sys.stdout.buffer.flush()
            line = remove_cursor_movements(line.replace(b'\r', b'').decode(errors='ignore').strip())
            self.runner_output.status(line)
        return stdout.channel.recv_exit_status() == 0
