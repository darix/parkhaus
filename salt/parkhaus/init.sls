#!py
#
# parkhaus
#
# Copyright (C) 2025   darix
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import logging
import salt.serializers.tomlmod as tomlmod
from salt.exceptions import SaltConfigurationError

log = logging.getLogger(__name__)

garage_config_path = "/etc/garage/garage.toml"

def run():
  config = {}

  if "garage" in __pillar__:
        python_version = __salt__["grains.get"]("pythonversion")
        garage_packages = ["garage", f"python{python_version[0]}{python_version[1]}-toml"]

        config["garage_packages"] = {
            "pkg.latest": [
                {'pkgs': garage_packages},
            ]
        }
        if "config" in __pillar__["garage"]:
            storage_dir   = __pillar__["garage"].get("storage_dir", "/var/lib/garage")
            garage_config = __pillar__["garage"]["config"]

            if not("metadata_dir" in garage_config):
                garage_config["metadata_dir"] = f"{storage_dir}/meta"

            if not("data_dir" in garage_config):
                garage_config["data_dir"] = f"{storage_dir}/data"

            # if not("bootstrap_peers" in garage_config):
            #     bootstrap_role          = __salt__["pillar.get"]("garage:bootstrap_role", None)
            #     bootstrap_mine_function = __salt__["pillar.get"]("garage:bootstrap_mine_function", None)

            #     if (bootstrap_role is None) or (bootstrap_mine_function is None):
            #         bootstrap_peers = []
            #         raise SaltConfigurationError("garage:config:bootstrap_peers is not set and garage:bootstrap_role + garage:bootstrap_mine_function are also not set")
            #         bootstrap_peers = __salt__['mine.get'](f"I@role:{bootstrap_role}", bootstrap_mine_function, tgt_type='compound')


            config["garage_config"] = {
                "file.managed": [
                    { "name": garage_config_path },
                    { "user": "root" },
                    { "group": "garage" },
                    { "mode":  "0640" },
                    { "require": ["garage_packages"] },
                    # { "template": "jinja" },
                    # { "source": "salt://parkhaus/files/etc/garage/garage.toml.j2" },
                    { "contents": tomlmod.serialize(garage_config) },
                    { "context": { "config": garage_config }},
                ]
            }

            config["garage_storage_dir"] = {
                "file.directory": [
                    { "name": storage_dir },
                    { "user": "garage" },
                    { "group": "garage" },
                    { "mode":  "0750" },
                    { "require": ["garage_packages"] },
                ]
            }

            config["garage_metadata_dir"] = {
                "file.directory": [
                    { "name": garage_config["metadata_dir"] },
                    { "user": "garage" },
                    { "group": "garage" },
                    { "mode":  "0750" },
                    { "require": ["garage_storage_dir"] },
                ]
            }

            config["garage_data_dir"] = {
                "file.directory": [
                    { "name": garage_config["data_dir"] },
                    { "user": "garage" },
                    { "group": "garage" },
                    { "mode":  "0750" },
                    { "require": ["garage_storage_dir"] },
                ]
            }

            # TODO:
            # {{ cfg.config.metadata_dir }}/node_key:
            # file.decode:
            #     - encoding_type: base64
            #     - contents_pillar: garage:node_key_base64
            #     - require:
            #     - file: {{ cfg.config.metadata_dir }}

            # {{ cfg.config.metadata_dir }}/node_key.pub:
            # file.decode:
            #     - encoding_type: base64
            #     - contents_pillar: garage:node_key_pub_base64
            #     - require:
            #     - file: {{ cfg.config.metadata_dir }}

            # permissions_{{ cfg.config.metadata_dir }}/node_key:
            # file.managed:
            #     - name: {{ cfg.config.metadata_dir }}/node_key
            #     - user: garage
            #     - group: garage
            #     - mode: '0600'

            # permissions_{{ cfg.config.metadata_dir }}/node_key.pub:
            # file.managed:
            #     - name: {{ cfg.config.metadata_dir }}/node_key.pub
            #     - user: garage
            #     - group: garage
            #     - mode: '0600'
            config["garage_service"] = {
                "service.running": [
                    { "name": "garage.service" },
                    { "enable": True },
                    { "watch": ["garage_config"] },
                    { "require": ["garage_data_dir", "garage_metadata_dir", "garage_config"] },
                ]
            }

            base_deps=["garage_service"]

            if __salt__['pillar.get']('garage:layout:apply', False):
                base_deps.append("garage_setup_layout")
                config["garage_setup_layout"] = {
                    "garage.layout_assignment": [
                        {'capacity': __salt__['pillar.get']('garage:layout:capacity')},
                        {'zone': __salt__['pillar.get']('garage:layout:zone')},
                        {'tags': __salt__['pillar.get']('garage:layout:tags', [])},
                        {'require': ["garage_service"]},
                    ]
                }

            garage_keys_pillar_path = 'garage:keys'
            current_garage_keys = [x['id'] for x in __salt__['garage.list_keys']()]
            pillar_garage_keys  = __salt__['pillar.get'](garage_keys_pillar_path, {})

            created_keys = []

            if isinstance(pillar_garage_keys, dict):
                for key_name, key_data in pillar_garage_keys.items():
                    key_section = f"garage_key_create_{key_name}"
                    config[key_section] = {
                        "garage.key_exists": [
                            {'name':       key_name},
                            {'key_id':     key_data['key_id']},
                            {'secret_key': key_data['secret_key']},
                            {'require':    base_deps},
                            {'current_garage_keys': current_garage_keys},
                        ]
                    }
                    created_keys.append(key_data['key_id'])
            elif isinstance(pillar_garage_keys, list):
                for key_data in pillar_garage_keys:
                    key_name = key_data['name']
                    key_section = f"garage_key_create_{key_name}"
                    config[key_section] = {
                        "garage.key_exists": [
                            {'name':       key_name},
                            {'key_id':     key_data['key_id']},
                            {'secret_key': key_data['secret_key']},
                            {'require':    base_deps},
                            {'current_garage_keys': current_garage_keys},
                        ]
                    }
                    ccreated_keys.append(key_data['key_id'])
            else:
                raise SaltConfigurationError(f"Do not know how to handle a {garage_keys_pillar_path} of {type(pillar_garage_keys)}")

            for key_id in [x for x in current_garage_keys if not(x in created_keys)]:
                config[f"garage_key_remove_{key_id}"] = {
                    "garage.key_absent": [
                        {'key_id': key_id},
                        {'require': base_deps},
                    ]
                }

  return config