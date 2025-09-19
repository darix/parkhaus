from subprocess import PIPE, Popen
import os
import logging
from salt.exceptions import SaltConfigurationError, SaltRenderError

garage_config_path = "/etc/garage/garage.toml"

log = logging.getLogger(__name__)

def layout_assignment(zone, datacenter):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}
  return ret