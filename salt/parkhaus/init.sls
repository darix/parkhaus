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

import re
import logging
import functools
import salt.serializers.tomlmod as tomlmod
from salt.exceptions import SaltConfigurationError

log = logging.getLogger(__name__)

garage_config_path = "/etc/garage/garage.toml"

def _this_is_first_peer():
    bootstrap_peers = __salt__['pillar.get']("garage:config:bootstrap_peers", [])
    if len(bootstrap_peers) == 0:
        return False

    boostrap_peer_re = re.compile(r'^(?P<key_spec>\S+)@(?P<host>[^:]+):(?P<port>\d+)$')
    mo = boostrap_peer_re.match(bootstrap_peers[0])
    if mo:
        return mo.group('host') == __salt__['grains.get']('fqdn')
    return False

def _update_settings_on_bucket(config, bucket_section, bucket_name, bucket_data):

  bucket_result = __salt__['garage.get_uri_path']("/v2/GetBucketInfo", {'globalAlias': bucket_name})
  if bucket_result.status_code == 200:
    bucket_info = bucket_result.json()

    keys_to_assign = bucket_data.get('keys', {})
    keys_assigned = keys_to_assign.keys()

    for key_block in bucket_info.get('keys', []):
        key_name = key_block['name']
        if not(key_name in keys_assigned):
            config[f"garage_bucket_drop_key_{bucket_name}_{key_name}"] = {
                "garage.bucket_key_assignment_absent": [
                    {'key_name':    key_name},
                    {'bucket_id':   bucket_info['id']},
                    {'accessKeyId': key_block['accessKeyId']},
                    {'permissions': key_block['permissions']},
                    {'require':     [bucket_section]},
                ]
            }

    for key_name, key_permissions in keys_to_assign.items():
        config[f"garage_bucket_assign_key_{bucket_name}_{key_name}"] = {
            "garage.bucket_key_assignment_present": [
                {'bucket_info': bucket_info},
                {'key_name':    key_name},
                {'permissions': key_permissions},
                {'require':     [bucket_section]},
            ]
        }

    if 'config' in bucket_data:
        config[f"garage_bucket_update_config"] = {
            "garage.bucket_set_config": [
                {'bucket_info':   bucket_info},
                {'bucket_config': bucket_data['config']}
            ]
        }
  else:
    raise SaltConfigurationError(f"Can not bucket information for {bucket_name} {bucket_result.status_code}: {bucket_result.json()}")

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

            if _this_is_first_peer():

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

                if __salt__['pillar.get']('garage:purge_unmanaged_keys', False):
                    for key_id in [x for x in current_garage_keys if not(x in created_keys)]:
                        config[f"garage_key_remove_{key_id}"] = {
                            "garage.key_absent": [
                                {'key_id': key_id},
                                {'require': base_deps},
                            ]
                        }

                garage_buckets_pillar_path = 'garage:buckets'
                current_garage_buckets = __salt__['garage.list_buckets']()
                pillar_garage_buckets  = __salt__['pillar.get'](garage_buckets_pillar_path, {})

                created_buckets_aliases = []

                if isinstance(pillar_garage_buckets, dict):
                    for bucket_name, bucket_data in pillar_garage_buckets.items():
                        bucket_section = f"garage_bucket_create_{bucket_name}"
                        config[bucket_section] = {
                            "garage.bucket_exists": [
                                {'name':       bucket_name},
                                {'require':    base_deps},
                                {'current_garage_buckets': current_garage_buckets},
                            ]
                        }
                        _update_settings_on_bucket(config, bucket_section, bucket_name, bucket_data)

                        created_buckets_aliases.append(bucket_name)
                elif isinstance(pillar_garage_buckets, list):
                    for bucket_data in pillar_garage_buckets:
                        bucket_name = bucket_data['name']
                        bucket_section = f"garage_bucket_create_{bucket_name}"
                        config[bucket_section] = {
                            "garage.bucket_exists": [
                                {'name':       bucket_name},
                                {'require':    base_deps},
                                {'current_garage_buckets': current_garage_buckets},
                            ]
                        }
                        _update_settings_on_bucket(config, bucket_section, bucket_name, bucket_data)

                        created_buckets_aliases.append(bucket_name)
                else:
                    raise SaltConfigurationError(f"Do not know how to handle a {garage_buckets_pillar_path} of {type(pillar_garage_buckets)}")

                # created_buckets_aliases = []
                if __salt__['pillar.get']('garage:purge_unmanaged_buckets', False):
                    def has_no_active_alias(bucket_record, existing_alias_list):
                        return not(functools.reduce(lambda a,b: a & b, [(alias in existing_alias_list) for alias in bucket_record['globalAliases']]))

                    for bucket_data in current_garage_buckets:
                        if has_no_active_alias(bucket_data, created_buckets_aliases):
                            bucket_id = bucket_data["id"]
                            bucket_name = bucket_data["id"]
                            if len(bucket_data['globalAliases']) > 0:
                                bucket_name = bucket_data['globalAliases'][0]

                            config[f"garage_bucket_remove_{bucket_name}"] = {
                                "garage.bucket_absent": [
                                    {'bucket_id': bucket_id},
                                    {'require': base_deps},
                                ]
                            }

  return config