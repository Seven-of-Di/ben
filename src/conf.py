from configparser import ConfigParser
import os


def load(fnm: str) -> ConfigParser:
    conf = ConfigParser()
    with open(os.getcwd()+"\\"+"default.conf") as f:
        conf.read_file(f)
    return conf
