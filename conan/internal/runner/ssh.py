from pathlib import Path
from typing import Iterable, Optional
import fnmatch
import pathlib
import tempfile

from conan.api.output import Color, ConanOutput
from conan.errors import ConanException

import errno
import os
from io import BytesIO
import sys

from conan.internal.runner.output import RunnerOutput

def ssh_info(msg, error=False):
    fg=Color.BRIGHT_MAGENTA
    if error:
        fg=Color.BRIGHT_RED
    ConanOutput().status('\n┌'+'─'*(2+len(msg))+'┐', fg=fg)
    ConanOutput().status(f'| {msg} |', fg=fg)
    ConanOutput().status('└'+'─'*(2+len(msg))+'┘\n', fg=fg)

class SSHRunner:

    def __init__(self, conan_api, command, host_profile, build_profile, args, raw_args):
        try:
            from paramiko.config import SSHConfig
            from paramiko.client import SSHClient
        except ImportError:
            raise ConanException(
                "Paramiko is required for SSH runner. If conan is installed in a virtual environment, try to install "
                "the 'paramiko' package, or consider installing conan package with extra requires 'conan[runners]'"
            )
        self.conan_api = conan_api
        self.command = command
        self.host_profile = host_profile
        self.build_profile = build_profile
        self.remote_host_profile = None
        self.remote_build_profile = None
        self.remote_python_command = None
        self.remote_create_dir = None
        self.remote_is_windows = None
        self.args = args
        self.raw_args = raw_args
        self.ssh_config = None
        self.remote_workspace = None
        self.remote_conan = None
        self.remote_conan_home = None
        if host_profile.runner.get('use_ssh_config', False):
            ssh_config_file = Path.home() / ".ssh" / "config"
            ssh_config = SSHConfig.from_file(open(ssh_config_file))

        hostname = host_profile.runner.get("host") # TODO: this one is required
        if ssh_config and ssh_config.lookup(hostname):
            hostname = ssh_config.lookup(hostname)['hostname']

        # this self.client manages the main ssh connection
        self.ssh_client = SSHClient()
        self.ssh_client.load_system_host_keys()
        self.ssh_client.connect(hostname)
        self.runner_output = RunnerOutput(hostname)
        # This client manages just the sftp transfers
        # TODO: Integrate both client calls in one
        self.sftp_client = RemoteConnection(self.ssh_client, self.runner_output)


    def run(self, use_cache=True):
        ssh_info('Got to SSHRunner.run(), doing nothing')

        self.ensure_runner_environment()
        self.copy_working_conanfile_path()

        raw_args = self.raw_args
        raw_args[raw_args.index(self.args.path)] = self.remote_create_dir
        raw_args = " ".join(raw_args)

        _Path = pathlib.PureWindowsPath if self.remote_is_windows else pathlib.PurePath
        remote_json_output = _Path(self.remote_create_dir).joinpath("conan_create.json").as_posix()
        command = f"{self.remote_conan} create {raw_args} --format json > {remote_json_output}"

        ssh_info(f"Remote command: {command}")

        stdout, _ = self._run_command(command)
        first_line = True
        while not stdout.channel.exit_status_ready():
            line = stdout.channel.recv(1024)
            if first_line and self.remote_is_windows:
                # Avoid clearing and moving the cursor when the remote server is Windows
                # https://github.com/PowerShell/Win32-OpenSSH/issues/1738#issuecomment-789434169
                line = line.replace(b"\x1b[2J\x1b[m\x1b[H",b"")
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            first_line = False

        if stdout.channel.recv_exit_status() == 0:
            self.update_local_cache(remote_json_output)

        # self.client.close()
    def ensure_runner_environment(self):
        has_python3_command = False
        python_is_python3 = False

        _, _stdout, _stderr = self.ssh_client.exec_command("python3 --version")
        has_python3_command = _stdout.channel.recv_exit_status() == 0
        if not has_python3_command:
            _, _stdout, _stderr = self.ssh_client.exec_command("python --version")
            if _stdout.channel.recv_exit_status() == 0 and "Python 3" in _stdout.read().decode():
                python_is_python3 = True

        python_command = "python" if python_is_python3 else "python3"
        self.remote_python_command = python_command

        if not has_python3_command and not python_is_python3:
            raise ConanException("Unable to locate working Python 3 executable in remote SSH environment")

        # Determine if remote host is Windows
        _, _stdout, _ = self.ssh_client.exec_command(f'{python_command} -c "import os; print(os.name)"')
        if _stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to determine remote OS type")
        is_windows = _stdout.read().decode().strip() == "nt"
        self.remote_is_windows = is_windows

        # Get remote user home folder
        _, _stdout, _ = self.ssh_client.exec_command(f'{python_command} -c "from pathlib import Path; print(Path.home())"')
        if _stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to determine remote home user folder")
        home_folder = _stdout.read().decode().strip()

        # Expected remote paths
        remote_folder = Path(home_folder) / ".conan2remote"
        remote_folder = remote_folder.as_posix().replace("\\", "/")
        self.remote_workspace = remote_folder
        remote_conan_home = Path(home_folder) / ".conan2remote" / "conanhome"
        remote_conan_home = remote_conan_home.as_posix().replace("\\", "/")
        self.remote_conan_home = remote_conan_home
        ssh_info(f"Remote workfolder: {remote_folder}")

        # Ensure remote folders exist
        for folder in [remote_folder, remote_conan_home]:
            _, _stdout, _stderr = self.ssh_client.exec_command(f"""{python_command} -c "import os; os.makedirs('{folder}', exist_ok=True)""")
            if _stdout.channel.recv_exit_status() != 0:
                ssh_info(f"Error creating remote folder: {_stderr.read().decode()}")
                raise ConanException(f"Unable to create remote workfolder at {folder}")

        conan_venv = remote_folder + "/venv"
        if is_windows:
            conan_cmd = remote_folder + "/venv/Scripts/conan.exe"
        else:
            conan_cmd = remote_folder + "/venv/bin/conan"

        ssh_info(f"Expected remote conan home: {remote_conan_home}")
        ssh_info(f"Expected remote conan command: {conan_cmd}")

        # Check if remote Conan executable exists, otherwise invoke pip inside venv
        has_remote_conan = self.sftp_client.check_file_exists(conan_cmd)

        if not has_remote_conan:
            _, _stdout, _stderr = self.ssh_client.exec_command(f"{python_command} -m venv {conan_venv}")
            if _stdout.channel.recv_exit_status() != 0:
                ssh_info(f"Unable to create remote venv: {_stderr.read().decode().strip()}")

            if is_windows:
                python_command = remote_folder + "/venv" + "/Scripts" + "/python.exe"
            else:
                python_command = remote_folder + "/venv" + "/bin" + "/python"

            _, _stdout, _stderr = self.ssh_client.exec_command(f"{python_command} -m pip install git+https://github.com/conan-io/conan@feature/docker_wrapper")
            if _stdout.channel.recv_exit_status() != 0:
                # Note: this may fail on windows
                ssh_info(f"Unable to install conan in venv: {_stderr.read().decode().strip()}")

        remote_env = {
            'CONAN_HOME': remote_conan_home,
            'CONAN_RUNNER_ENVIRONMENT': "1"
        }
        if is_windows:
            # Wrapper script with environment variables preset
            env_lines = "\n".join([f"set {k}={v}" for k,v in remote_env.items()])
            conan_bat_contents = f"""@echo off\n{env_lines}\n{conan_cmd} %*\n"""
            conan_bat = remote_folder + "/conan.bat"
            try:
                sftp = self.ssh_client.open_sftp()
                sftp.putfo(BytesIO(conan_bat_contents.encode()), conan_bat)
            except:
                raise ConanException("unable to set up Conan remote script")
            finally:
                sftp.close()

            self.remote_conan = conan_bat
        _, _stdout, _stderr = self.ssh_client.exec_command(f"{self.remote_conan} config home")
        ssh_info(f"Remote conan config home returned: {_stdout.read().decode().strip()}")
        _, _stdout, _stderr = self.ssh_client.exec_command(f"{self.remote_conan} profile detect --force")
        self._sync_conan_config()

    def _sync_conan_config(self):
        # Transfer conan config to remote
        cache_home = Path(self.conan_api.config.home())
        cache_remote = Path(self.remote_conan_home)
        # TODO: inspect each file and determine if references to local paths are present -> inform
        # user that that profile/configuration file will not work on remote
        self.sftp_client.put_dir(
            cache_home / "profiles",
            cache_remote / "profiles",
            exclude_patterns=(".conan.db", "*.pyc", "__pycache__", ".DS_Store", ".git")
        )
        for file in ("settings.yml", "settings_user.yml", "global.conf", "remotes.json"):
            if (cache_home / file).exists():
                self.sftp_client.put(cache_home / file, cache_remote / file)

    def copy_working_conanfile_path(self):
        resolved_path = Path(self.args.path).resolve()
        if resolved_path.is_file():
            resolved_path = resolved_path.parent

        if not resolved_path.is_dir():
            return ConanException("Error determining conanfile directory")

        # Create temporary destination directory
        temp_dir_create_cmd = f"""{self.remote_python_command} -c "import tempfile; print(tempfile.mkdtemp(dir='{self.remote_workspace}'))"""
        _, _stdout, _ = self.ssh_client.exec_command(temp_dir_create_cmd)
        if _stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to create remote temporary directory")
        self.remote_create_dir = _stdout.read().decode().strip().replace("\\", '/')

        # Copy current folder to destination using sftp
        # self.remote_conn.put_dir(resolved_path.as_posix(), self.remote_create_dir)
        _Path = pathlib.PureWindowsPath if self.remote_is_windows else pathlib.PurePath
        sftp = self.ssh_client.open_sftp()
        for root, dirs, files in os.walk(resolved_path.as_posix()):
            relative_root = Path(root).relative_to(resolved_path)
            for dir in dirs:
                    dst = _Path(self.remote_create_dir).joinpath(relative_root).joinpath(dir).as_posix()
                    sftp.mkdir(dst)
            for file in files:
                orig = os.path.join(root, file)
                dst = _Path(self.remote_create_dir).joinpath(relative_root).joinpath(file).as_posix()
                sftp.put(orig, dst)
        sftp.close()

    def _run_command(self, command):
        ''' Run a command in an SSH session.
            When requesting a pseudo-terminal from the server,
            ensure we pass width and height that matches the current
            terminal
        '''
        channel = self.ssh_client.get_transport().open_session()
        if sys.stdout.isatty():
            width, height = os.get_terminal_size()
            channel.get_pty(width=width, height=height)

        channel.exec_command(command)

        stdout = channel.makefile("r")
        stderr = channel.makefile("r")
        return stdout, stderr

    def update_local_cache(self, json_result):
        # ('conan list --graph=create.json --graph-binaries=build --format=json > pkglist.json'
        _Path = pathlib.PureWindowsPath if self.remote_is_windows else pathlib.PurePath
        pkg_list_json = _Path(self.remote_create_dir).joinpath("pkg_list.json").as_posix()
        pkg_list_command = f"{self.remote_conan} list --graph={json_result} --graph-binaries=build --format=json > {pkg_list_json}"
        _, stdout, _ = self.ssh_client.exec_command(pkg_list_command)
        if stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to generate remote package list")

        conan_cache_tgz = _Path(self.remote_create_dir).joinpath("cache.tgz").as_posix()
        cache_save_command = f"{self.remote_conan} cache save --list {pkg_list_json} --file {conan_cache_tgz}"
        _, stdout, _ = self.ssh_client.exec_command(cache_save_command)
        if stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to save remote conan cache state")

        with tempfile.TemporaryDirectory() as tmp:
            local_cache_tgz = os.path.join(tmp, 'cache.tgz')
            self.sftp_client.get(conan_cache_tgz, local_cache_tgz)
            self.conan_api.cache.restore(local_cache_tgz)


class RemoteConnection:
    def __init__(self, ssh_client, runner_output: RunnerOutput):
        from paramiko.client import SSHClient
        self.client: SSHClient = ssh_client
        # No need to close connection as it will be closed on destroy of RemoteConnection
        self.sftp = self.client.open_sftp()
        self.runner_output = runner_output

    def put(self, src: Path, dst: Path) -> None:
        try:
            self.sftp.put(src.as_posix(), dst.as_posix())
            self.runner_output.verbose(f"Copying file {src.as_posix()} to {dst}")
        except IOError as e:
            self.runner_output.error(f"Unable to copy {src} to {dst}:\n{e}")

    def put_dir(self, source_folder: Path, destination_folder: Path, exclude_patterns: Optional[Iterable[str]] = None) -> None:
        for item in source_folder.iterdir():
            dest_item = destination_folder / item.name
            # Check if item matches any exclude pattern
            if exclude_patterns and any(fnmatch.fnmatch(item.name, pattern) for pattern in exclude_patterns):
                continue
            if item.is_file():
                self.runner_output.verbose(f"Copying file {item.as_posix()} to {dest_item}")
                self.put(item, dest_item)
            elif item.is_dir():
                self.runner_output.verbose(f"Copying directory {item.as_posix()} to {dest_item}")
                self.mkdir(dest_item, ignore_existing=True)
                self.put_dir(item, dest_item, exclude_patterns)

    def get(self, src: str, dst: str) -> None:
        try:
            self.sftp.get(src, dst)
        except IOError as e:
            self.runner_output.error(f"Unable to copy from remote {src} to {dst}:\n{e}")

    def mkdir(self, folder: Path, ignore_existing=False) -> None:
        try:
            self.sftp.mkdir(folder.as_posix())
        except IOError as e:
            if e.errno == errno.EEXIST and ignore_existing:
                pass
            else:
                raise

    def check_file_exists(self, file: str) -> bool:
        try:
            self.sftp.stat(file)
            return True
        except FileNotFoundError:
            return False
