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
    "-a", "--authorize",
    action="store_true",
    help="authenticate using credentials from the configuration.\nWARNING: this will log you out of your local docker"
)

pipeline_arguments = parser.add_argument_group("pipeline")

pipeline_arguments.add_argument(
    "-d", "--default",
    action="store_true",
    help="run the default pipeline"
)

pipeline_arguments.add_argument(
    "-p", "--pull-request",
    help="run a pull-request pipeline",
    metavar="PULL_REQUEST"
)

pipeline_arguments.add_argument(
    "-b", "--branch",
    help="run a branch pipeline",
    metavar="BRANCH"
)

pipeline_arguments.add_argument(
    "-t", "--tag",
    help="run a tag pipeline",
    metavar="TAG"
)

pipeline_arguments.add_argument(
    "-c", "--custom",
    help="run a custom pipeline",
    metavar="CUSTOM"
)

parser.add_argument(
    "Directory",
    help="working directory that contains the bitbucket-pipelines.yml to run"
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

def is_valid_git_repository(path: str) -> bool:
    result = subprocess.run(["git", "ls-remote", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return result.returncode == 0

def execute_steps(pipeline): 
    steps = get_steps(pipeline) 
 
    if authorized: 
        docker_logout() 
 
    docker_execute_step(image, steps, max_time, authorized, directory) 
 
    if authorized: 
        docker_logout() 
#endregion

#region Docker
def docker_start_step(image: Image, directory: str):
    step_result = subprocess.run(["docker", "run", "-di", image.name], stdout=subprocess.PIPE, text=True)

    container_id = step_result.stdout.splitlines()[0]

    subprocess.run(["docker", "exec", "-i", container_id, "mkdir", "-p", "/opt/atlassian/pipelines/agent/build"], stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "cp", directory, "{0}:/opt/atlassian/pipelines/agent/build".format(container_id)], stdout=subprocess.DEVNULL)

    return container_id

def docker_execute_step(image: Image, step, max_time, authorized: bool, directory: str):
    def execute_step():
        script = step["script"]

        for command in script:
            executable_command = "docker exec -i " + container_id + " " + command
            subprocess.run(executable_command)

    if isinstance(step, list):
        for sub_step in step:
            docker_execute_step(image, sub_step, max_time, authorized, directory)
    elif "script" in step:
        step_image = get_image(step, image)

        if authorized \
            and step_image.username is not None \
            and step_image.password is not None:
            docker_login(step_image.username, step_image.password)

        container_id = docker_start_step(step_image, directory)
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
    subprocess.run(["docker", "login", "-u", username, "-p", password])

def docker_logout():
    subprocess.run(["docker", "logout"], stdout=subprocess.DEVNULL)
#endregion

directory = arguments.Directory

cannot_run = False

if shutil.which("docker") is None:
    print("Docker needs to be installed for this program to work")
    cannot_run = True

if shutil.which("git") is None:
    print("Git needs to be installed for this program to work")
    cannot_run = True

if cannot_run:
    exit(1)

if not is_valid_git_repository(directory):
    print("Directory \"{0}\" is not a valid Git directory".format(directory))
    exit(1)

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

pipeline_sum = sum(
    [
        arguments.default,
        arguments.pull_request is not None,
        arguments.branch is not None,
        arguments.tag is not None,
        arguments.custom is not None
    ]
)

if pipeline_sum > 1:
    print("ERROR: Can only specify one pipeline to run")
    exit(1)

if pipeline_sum == 0:
    print("ERROR: Must specify pipeline to run\n")

    parser.print_help()

if arguments.default:
    if "default" not in pipelines:
        print("Default section needs to be configured in YAML")
        exit(1)
    
    default = pipelines["default"]

    execute_steps(default)

if arguments.pull_request is not None:
    if "pull-requests" not in pipelines:
        print("Pull-requests section needs to be configured in YAML")
        exit(1)

    pull_requests = pipelines["pull-requests"]

    if arguments.pull_request not in pull_requests:
        print("Pull-request \"{0}\" not configured in YAML".format(arguments.pull_request))
        exit(1)
    
    pull_request = pull_requests[arguments.pull_request]

    execute_steps(pull_request)

if arguments.branch is not None:
    if "branches" not in pipelines:
        print("Branches section needs to be configured in YAML")
        exit(1)

    branches = pipelines["branches"]

    if arguments.branch not in branches:
        print("Branch \"{0}\" not configured in YAML".format(arguments.branch))
        exit(1)
    
    branch = branches[arguments.branch]

    execute_steps(branch)

if arguments.tag is not None:
    if "tags" not in pipelines:
        print("Tags section needs to be configured in YAML")
        exit(1)

    tags = pipelines["tags"]

    if arguments.tag not in tags:
        print("Tag \"{0}\" not configured in YAML".format(arguments.tag))
        exit(1)
    
    tag = tags[arguments.tag]

    execute_steps(tag)

if arguments.custom is not None:
    if "custom" not in pipelines:
        print("Custom section needs to be configured in YAML")
        exit(1)

    custom = pipelines["custom"]

    if arguments.custom not in custom:
        print("Custom \"{0}\" not configured in YAML".format(arguments.custom))
        exit(1)
    
    custom_pipeline = custom[arguments.custom]

    execute_steps(custom_pipeline)