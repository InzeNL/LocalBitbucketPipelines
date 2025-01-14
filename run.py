import yaml

document = yaml.load(open("bitbucket-pipelines.yml").read(), Loader=yaml.CLoader)
