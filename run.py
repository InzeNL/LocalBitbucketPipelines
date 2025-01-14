import yaml

document = yaml.load(open("bitbucket-pipelines.yml").read(), Loader=yaml.CLoader)

if document["pipelines"] is None:
    print("Missing required property 'pipelines'")

    exit(1)