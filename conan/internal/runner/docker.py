import os
import json
from io import BytesIO
import textwrap
import shutil

from conan.api.model import ListPattern
from conan.api.output import ConanOutput
from conan.api.conan_api import ConfigAPI


class DockerRunner:

    def __init__(self, conan_api, profile, args, raw_args):
        import docker
        self.conan_api = conan_api
        self.args = args
        self.raw_args = raw_args
        self.docker_client = docker.from_env()
        self.docker_api = docker.APIClient()
        self.dockerfile = str(profile.runner.get('dockerfile', ''))
        self.image = str(profile.runner.get('image', 'conanrunner'))
        self.cache = str(profile.runner.get('cache', 'copy'))
        self.runner_home = os.path.join(args.path, '.conanrunner')

    def run(self):
        """
        run conan inside a Docker continer
        """
        ConanOutput().info(msg=f'\nBuilding the Docker image: {self.image}')
        self.build_image()
        ConanOutput().info(msg=f'\nInit container resources')
        command, volumes, environment = self.create_runner_environment()
        # Init docker python api
        ConanOutput().info(msg=f'\nRunning the Docker container\n')
        container = self.docker_client.containers.run(self.image,
                                                      command,
                                                      volumes=volumes,
                                                      environment=environment,
                                                      detach=True)
        for line in container.attach(stdout=True, stream=True, logs=True):
            ConanOutput().info(line.decode('utf-8', errors='ignore').strip())
        container.wait()
        container.stop()
        container.remove()
        self.update_local_cache()

    def build_image(self):
        docker_build_logs = None
        if self.dockerfile:
            docker_build_logs = self.docker_api.build(path=self.dockerfile, tag=self.image)
        else:
            dockerfile = textwrap.dedent("""
                FROM ubuntu
                RUN apt update && apt upgrade -y
                RUN apt install -y build-essential
                RUN apt install -y python3-pip cmake git
                RUN cd /root && git clone https://github.com/davidsanfal/conan.git conan-io
                RUN cd /root/conan-io && pip install -e .
                """)

            docker_build_logs = self.docker_api.build(fileobj=BytesIO(dockerfile.encode('utf-8')),
                                                      nocache=False,
                                                      tag=self.image)
        for chunk in docker_build_logs:
            for line in chunk.decode("utf-8").split('\r\n'):
                if line:
                    stream = json.loads(line).get('stream')
                    if stream:
                        ConanOutput().info(stream.strip())

    def create_runner_environment(self):
        volumes = {self.args.path: {'bind': self.args.path, 'mode': 'rw'}}
        environment = {'CONAN_REMOTE_ENVIRONMNET': '1'}

        if self.cache == 'shared':
            volumes[ConfigAPI(self.conan_api).home()] = {'bind': '/root/.conan2', 'mode': 'rw'}
            command = ' '.join(['conan create'] + self.raw_args)

        if self.cache in ['clean', 'copy']:
            shutil.rmtree(self.runner_home, ignore_errors=True)
            os.mkdir(self.runner_home)
            shutil.copytree(os.path.join(ConfigAPI(self.conan_api).home(), 'profiles'), os.path.join(self.runner_home, 'profiles'))
            environment['CONAN_REMOTE_COMMAND'] = ' '.join(['conan create'] + self.raw_args)
            environment['CONAN_REMOTE_WS'] = self.args.path
            command = f'/bin/bash {os.path.join(self.runner_home, "conan-runner-init.sh")}'
            conan_runner_init = textwrap.dedent("""
                mkdir -p ${HOME}/.conan2/profiles
                echo "Updating profiles ..."
                cp -r ${CONAN_REMOTE_WS}/.conanrunner/profiles/. -r ${HOME}/.conan2/profiles/.
                echo "Running: ${CONAN_REMOTE_COMMAND}"
                eval "${CONAN_REMOTE_COMMAND}"
                """)
            if self.cache == 'copy':
                tgz_path = os.path.join(self.runner_home, 'conan_cache_save.tgz')
                self.conan_api.cache.save(self.conan_api.list.select(ListPattern("*")), tgz_path)
                conan_runner_init = textwrap.dedent("""
                    conan cache restore ${CONAN_REMOTE_WS}/.conanrunner/conan_cache_save.tgz
                    """) + conan_runner_init + textwrap.dedent("""
                    conan cache save "*" --file ${CONAN_REMOTE_WS}/.conanrunner/conan_cache_docker.tgz
                    """)
            with open(os.path.join(self.runner_home, 'conan-runner-init.sh'), 'w+') as f:
                conan_runner_init = textwrap.dedent("""#!/bin/bash
                    """) + conan_runner_init
                print(conan_runner_init)
                f.writelines(conan_runner_init)

        return command, volumes, environment

    def update_local_cache(self):
        if self.cache == 'copy':
            tgz_path = os.path.join(self.runner_home, 'conan_cache_docker.tgz')
            package_list = self.conan_api.cache.restore(tgz_path)
