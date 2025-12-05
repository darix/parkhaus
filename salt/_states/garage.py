import os
import logging
import requests
import re
import json
from salt.exceptions import SaltConfigurationError, SaltRenderError

garage_config_path = "/etc/garage/garage.toml"

log = logging.getLogger(__name__)

def _get_admin_url():
  api_bind_addr_pillar_path = 'garage:config:admin:api_bind_addr'
  api_bind_addr = __salt__['pillar.get'](api_bind_addr_pillar_path, None)
  if api_bind_addr is None:
    raise SaltConfigurationError(f"Could not fetch the api_bind_addr via {api_bind_addr_pillar_path}")

  port_re = re.compile(r'^(?P<bind_spec>\S+):(?P<port>\d+)$')
  mo = port_re.match(api_bind_addr)
  if mo:
    if mo.group('bind_spec') == '[::]':
      return f"http://localhost:{mo.group('port')}"
    else:
      return f"http://{mo.group('bind_spec')}:{mo.group('port')}"
  else:
    raise SaltConfigurationError(f"Could not parse '{api_bind_addr}' with {port_re}")

def _get_full_url(uri_path):
  return f"{_get_admin_url()}{uri_path}"

def _auth_header(extra_headers={}):
  rpc_secret  = __salt__['pillar.get']('garage:config:rpc_secret', None)
  if rpc_secret is None:
    raise SaltConfigurationError(f"Could not rpc_secret in the pillar")

  auth_header = {"Authorization": f"Bearer {rpc_secret}"}
  if len(extra_headers) > 0:
    auth_header.update(extra_headers)
  return auth_header

def _get_uri_path(uri_path):
    full_url = _get_full_url(uri_path)
    result = requests.get(full_url, headers=_auth_header())
    log.error(f"get_uri_path: reponse {result.status_code} json: {result.json()}")
    return result

def _post_uri_path(uri_path, post_data, content_type='application/json'):
    full_url = _get_full_url(uri_path)
    log.error(f"post_data: {post_data}")
    json_post_data = json.dumps(post_data, indent=2)
    headers = _auth_header({'content-type': content_type})
    result = requests.post(full_url, headers=headers, data=json_post_data)
    log.error(f"post_uri_path: reponse {result.status_code} json: {result.json()}")
    return result

def _update_layout_data(current_node_data, new_node_data):
  new_node_list = []
  for node_data in current_node_data:
    new_node = {
      'id': node_data['id'],
    }
    for field in ['capacity', 'zone', 'tags']:
      new_node[field] = new_node_data.get(field, node_data[field])
    new_node_list.append(new_node)
  return new_node_list

def layout_assignment(name, capacity, zone, tags=[]):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}

  current_cluster_layout_result = _get_uri_path("/v2/GetClusterLayout")
  current_cluster_layout = current_cluster_layout_result.json()

  all_correct = True
  for node in current_cluster_layout['roles']:
    if not(node['capacity'] == capacity and node['zone'] == zone and node['tags'] == tags):
      all_correct = False
      break

  if all_correct:
    ret["result"] = True
    ret["comment"] = "Layout is already correct. You can manually verify it with 'garage layout show'"
  else:
    if __opts__["test"]:
      ret["comment"] = f"Layout needs updating"
    else:
      new_data = {
        'roles': _update_layout_data(
          current_cluster_layout['roles'],
          {'capacity': capacity, 'zone': zone, 'tags': tags}
        )
      }
      post_result = _post_uri_path('/v2/UpdateClusterLayout', new_data)
      if post_result.status_code == 200:
        if len(post_result.json()['stagedRoleChanges']) > 0:
          new_version = post_result.json()['version'] + 1
          apply_result =  _post_uri_path('/v2/ApplyClusterLayout', {'version': new_version})
          if apply_result.status_code == 200:
            ret["result"] = True
            ret["changes"][name] = "".join(apply_result.json()['message'])
          else:
            ret["result"] = False
            ret["comment"] = "Something failed during apply cluster layout. Please check 'garage layout show' and 'garage layout history'"
        else:
          ret["result"] = True
          ret["comment"] = "Layout is already correct. You can manually verify it with 'garage layout show'"
      else:
        ret["result"] = False
        ret["comment"] = f"Error while updating the cluster layout: {post_result.json()} {new_data}"
  return ret