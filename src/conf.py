from configparser import ConfigParser
import os


def load(fnm: str) -> ConfigParser:
    conf = ConfigParser()
    if __debug__:
        fnm = os.getcwd()+"\\"+"default.conf"
    with open(fnm) as f:
        conf.read_file(f)
    return conf
