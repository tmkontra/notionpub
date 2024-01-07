from typing import Union, List

import pydantic
import yaml


@pydantic.dataclasses.dataclass
class ConfigFile:
    root_page_id: str
    paths: List[Union[str, dict]]


def load_config(file):
    contents = yaml.safe_load(file)
    try:
        cfg = ConfigFile(**contents)
    except pydantic.ValidationError:
        raise
    return cfg
