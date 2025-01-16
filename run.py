import yaml
import argparse
import jsonschema
import json
import shutil
import subprocess

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
#endregion

#region Docker
def docker_start_step(image):
    step_result = subprocess.run(["docker", "run", "-di", image], stdout=subprocess.PIPE, text=True)

    return step_result.stdout.splitlines()[0]

def docker_execute_step(container_id, step):
    if isinstance(step, list):
        for sub_step in step:
            docker_execute_step(container_id, sub_step)
    elif "script" in step:
        script = step["script"]
        for command in script:
            executable_command = "docker exec -i " + container_id + " " + command
            subprocess.run(executable_command)

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

if "image" in document:
    image = document["image"]
else:
    image = "atlassian/default-image:latest"

if arguments.default:
    if "default" not in pipelines:
        print("Default needs to be set")
        exit(1)
    
    default = pipelines["default"]

    steps = get_steps(default)

    for step in steps:
        container_id = docker_start_step(image)
        docker_execute_step(container_id, step)

        docker_kill_step(container_id)