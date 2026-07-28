import config
from openai import OpenAI
import json

def default_setup():
    # JSON file read
    with open('plot.json') as f:
        config.json_value = json.load(f)

