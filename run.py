import yaml
import argparse
import jsonschema
import json
import shutil
import subprocess
import threading

#region Arguments
parser = argparse.ArgumentParser(
    prog='Bitbucket Pipelines Runner',
    description='Allows users to run Bitbucket Pipelines locally')

parser.add_argument(
    "-d", "--default",
    action="store_true",
    help="Run the default pipeline"
)

arguments = parser.parse_args()
#endregion

#region Classes
class Image:
    def __init__(self, name: str, username: str, password: str, run_as_user: str):
        self.name = name
        self.username = username
        self.password = password
        self.run_as_user = run_as_user
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
#endregion

#region Docker
def docker_start_step(image: Image):
    step_result = subprocess.run(["docker", "run", "-di", image.name], stdout=subprocess.PIPE, text=True)

    return step_result.stdout.splitlines()[0]

def docker_execute_step(image: Image, step, max_time):
    def execute_step():
        script = step["script"]

        for command in script:
            executable_command = "docker exec -i " + container_id + " " + command
            subprocess.run(executable_command)

    if isinstance(step, list):
        for sub_step in step:
            docker_execute_step(image, sub_step, max_time)
    elif "script" in step:
        container_id = docker_start_step(image)
        try:
            if "max-time" in step: 
                max_time = int(step["max-time"]) 
    
            thread = threading.Thread(target=execute_step) 
            thread.start() 
            thread.join(max_time * 60) 
            
            if thread.is_alive(): 
                print("Step timed out") 
        finally:
            docker_kill_step(container_id)

def docker_kill_step(container_id):
    subprocess.run(["docker", "kill", container_id], stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "rm", container_id], stdout=subprocess.DEVNULL)
#endregion

if shutil.which("docker") is None:
    print("Docker needs to be installed for this program to work")

document = yaml.load(open("bitbucket-pipelines.yml").read(), Loader=yaml.CLoader)
schema = json.loads(open("schema.json").read())

jsonschema.validate(document, schema)

if "pipelines" not in document:
    print("Pipelines need to be set")
    exit(1)

pipelines = document["pipelines"]

image = get_image(document)
max_time = 120 

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

    docker_execute_step(image, steps, max_time)