import yaml
import argparse
import jsonschema
import json
import shutil
import subprocess
import threading
import os

#region Arguments
parser = argparse.ArgumentParser(
    prog='Bitbucket Pipelines Runner',
    description='Allows users to run Bitbucket Pipelines locally',
    formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument(
    "-d", "--default",
    action="store_true",
    help="Run the default pipeline"
)

parser.add_argument(
    "-a", "--authorize",
    action="store_true",
    help="Authenticate using credentials from the configuration.\nWARNING: This will log you out of your local docker"
)

parser.add_argument(
    "Directory",
    help="Working directory to run the pipelines for"
)

arguments = parser.parse_args()
#endregion

#region Classes
class Image:
    def __init__(self, name: str, username: str, password: str, run_as_user: str):
        self.name = expand_variables(name)
        self.username = expand_variables(username)
        self.password = expand_variables(password)
        self.run_as_user = expand_variables(run_as_user)
#endregion

#region Functions
def get_steps(pipelines):
    if pipelines is None:
        return []

    steps = []

    for potential_step in pipelines:
        if "step" in potential_step:
            steps.append(potential_step["step"])
        if "parallel" in potential_step:
            parallel = potential_step["parallel"]

            if "steps" in parallel:
                steps.append(get_steps(parallel["steps"]))

    return steps

def get_image(step, default: Image = None) -> Image:
    if default is None:
        default = Image("atlassian/default-image:latest", None, None, None)

    if "image" in step:
        image = step["image"]

        if isinstance(image, str):
            return Image(image, None, None, None)
        else:
            image_name = "atlassian/default-image:latest";
            image_username = None
            image_password = None
            image_run_as_user = None

            if "name" in image:
                image_name = image["name"]
            if "username" in image:
                image_username = image["username"]
            if "password" in image:
                image_password = image["password"]
            if "run-as-user" in image:
                image_run_as_user = image["run-as-user"]

            return Image(image_name, image_username, image_password, image_run_as_user)
    else:
        return default
    
def expand_variables(string: str|None) -> str|None:
    if string is None:
        return None

    return os.path.expandvars(string)
#endregion

#region Docker
def docker_start_step(image: Image):
    step_result = subprocess.run(["docker", "run", "-di", image.name], stdout=subprocess.PIPE, text=True)

    return step_result.stdout.splitlines()[0]

def docker_execute_step(image: Image, step, max_time, authorized: bool):
    def execute_step():
        script = step["script"]

        for command in script:
            executable_command = "docker exec -i " + container_id + " " + expand_variables(command)
            subprocess.run(executable_command)

    if isinstance(step, list):
        for sub_step in step:
            docker_execute_step(image, sub_step, max_time, authorized)
    elif "script" in step:
        step_image = get_image(step, image)

        if authorized \
            and step_image.name is not None \
            and step_image.password is not None:
            docker_login(step_image.name, step_image.password)

        container_id = docker_start_step(step_image)
        try:
            if "max-time" in step: 
                max_time = int(step["max-time"]) 
    
            thread = threading.Thread(target=execute_step) 
            thread.start() 
            thread.join(max_time * 60) 
            
            if thread.is_alive(): 
                print("Step timed out") 
        finally:
            if authorized:
                docker_logout()
            docker_kill_step(container_id)

def docker_kill_step(container_id):
    subprocess.run(["docker", "kill", container_id], stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "rm", container_id], stdout=subprocess.DEVNULL)

def docker_login(username: str, password: str):
    subprocess.run(["docker", "login", "-u \"{0}\"".format(username), "-p \"{0}\"".format(password)])

def docker_logout():
    subprocess.run(["docker", "logout"], stdout=subprocess.DEVNULL)
#endregion

directory = arguments.Directory

if shutil.which("docker") is None:
    print("Docker needs to be installed for this program to work")

document = yaml.load(open(os.path.join(directory, "bitbucket-pipelines.yml")).read(), Loader=yaml.CLoader)
schema = json.loads(open("schema.json").read())

jsonschema.validate(document, schema)

if "pipelines" not in document:
    print("Pipelines need to be set")
    exit(1)

pipelines = document["pipelines"]

image = get_image(document)
max_time = 120

authorized = arguments.authorize

if "options" in document: 
    options = document["options"] 
 
    if "max-time" in options: 
        max_time = int(options["max-time"]) 

if arguments.default:
    if "default" not in pipelines:
        print("Default needs to be set")
        exit(1)
    
    default = pipelines["default"]

    steps = get_steps(default)

    if authorized:
        docker_logout()

    docker_execute_step(image, steps, max_time, authorized)

    if authorized:
        docker_logout()