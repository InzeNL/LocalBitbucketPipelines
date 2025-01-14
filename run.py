import yaml
import argparse

parser = argparse.ArgumentParser(
    prog='Bitbucket Pipelines Runner',
    description='Allows users to run Bitbucket Pipelines locally')

parser.parse_args()

document = yaml.load(open("bitbucket-pipelines.yml").read(), Loader=yaml.CLoader)

if document["pipelines"] is None:
    print("Missing required property 'pipelines'")

    exit(1)
    
pipelines = document["pipelines"]

if "default" not in pipelines \
    and "branches" not in pipelines \
    and "tags" not in pipelines \
    and "bookmarks" not in pipelines \
    and "custom" not in pipelines \
    and "pull-requests" not in pipelines:
        print("'pipelines' requires at least a default, branches, tags, bookmarks or custom section")