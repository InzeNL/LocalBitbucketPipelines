import yaml
import argparse
import jsonschema
import json

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

document = yaml.load(open("bitbucket-pipelines.yml").read(), Loader=yaml.CLoader)
schema = json.loads(open("schema.json").read())

jsonschema.validate(document, schema)

if arguments.default:
    print("Running default pipeline")