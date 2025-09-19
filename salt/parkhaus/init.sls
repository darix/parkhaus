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

import salt.serializers.tomlmod as tomlmod

def run():
  config = {}
  if "garage" in __pillar__:
        garage_packages = ["garage"]
        config["garage_packages"] = {
            "pkg.latest": [
                {'pkgs': garage_packages},
            ]
        }
        if "config" in __pillar__["garage"]:
            storage_dir   = __pillar__["garage"]["storage_dir"]
            garage_config = __pillar__["garage"]["config"]

            if not("metadata_dir" in garage_config):
                garage_config["metadata_dir"] = f"{storage_dir}/metadata"

            if not("data_dir" in garage_config):
                garage_config["data_dir"] = f"{storage_dir}/data"

            config["garage_config"] = {
                "file.managed": [
                    { "name": "/etc/garage/garage.toml" },
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

            recurse_attributes = ["user", "group", "mode"]

            config["garage_storage_dir"] = {
                "file.directory": [
                    { "name": storage_dir },
                    { "user": "garage" },
                    { "group": "garage" },
                    { "mode":  "0750" },
                    { "recurse": recurse_attributes },
                    { "require": ["garage_packages"] },
                ]
            }

            config["garage_metadata_dir"] = {
                "file.directory": [
                    { "name": garage_config["metadata_dir"] },
                    { "user": "garage" },
                    { "group": "garage" },
                    { "mode":  "0750" },
                    { "recurse": recurse_attributes },
                    { "require": ["garage_storage_dir"] },
                ]
            }

            config["garage_data_dir"] = {
                "file.directory": [
                    { "name": garage_config["data_dir"] },
                    { "user": "garage" },
                    { "group": "garage" },
                    { "mode":  "0750" },
                    { "recurse": recurse_attributes },
                    { "require": ["garage_storage_dir"] },
                ]
            }

            config["garage_service"] = {
                "service.running": [
                    { "name": "garage.service" },
                    { "enable": True },
                    { "watch": ["garage_config"] },
                    { "require": ["garage_data_dir", "garage_metadata_dir", "garage_config"] },
                ]
            }

  return config
