import yaml


with open('./config.yaml', encoding='utf-8') as file:
    config = yaml.safe_load(file)
