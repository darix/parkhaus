from subprocess import PIPE, Popen
import os
import logging
from salt.exceptions import SaltConfigurationError, SaltRenderError

garage_config_path = "/etc/garage/garage.toml"

log = logging.getLogger(__name__)

def _run_subcommand(sub_command_list):
    cmd = ["/usr/bin/garage", f"--config={garage_config_path}"]
    cmd.extend(sub_command_list)

    log.error(f"cmd: {cmd}")
    try:
        env = os.environ.copy()
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, env=env, encoding="utf-8")
        cmd_output_data, cmd_error_code = proc.communicate()
        pass_returncode = proc.returncode
    except (OSError, UnicodeDecodeError) as e:
        cmd_output_data, cmd_error_code = "", str(e)
        pass_returncode = 1

    # The version of pass used during development sent output to
    # stdout instead of stderr even though its returncode was non zero.
    if pass_returncode or not cmd_output_data:
        log.error(f"something failed while running garage: c:{pass_returncode} d:{cmd_output_data}")
    return cmd_output_data.rstrip("\r\n")