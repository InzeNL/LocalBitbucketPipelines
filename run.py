import yaml
import argparse
import jsonschema
import json

parser = argparse.ArgumentParser(
    prog='Bitbucket Pipelines Runner',
    description='Allows users to run Bitbucket Pipelines locally')

parser.parse_args()

document = yaml.load(open("bitbucket-pipelines.yml").read(), Loader=yaml.CLoader)
schema = json.loads(open("schema.json").read())

jsonschema.validate(document, schema)