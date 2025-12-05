import os
import logging
import requests
import re
import json
from salt.exceptions import SaltConfigurationError, SaltRenderError

log = logging.getLogger(__name__)

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

  current_cluster_layout_result = __salt__['garage.get_uri_path']("/v2/GetClusterLayout")
  if current_cluster_layout_result.status_code == 200:
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
        post_result = __salt__['garage.post_uri_path']('/v2/UpdateClusterLayout', new_data)
        if post_result.status_code == 200:
          if len(post_result.json()['stagedRoleChanges']) > 0:
            new_version = post_result.json()['version'] + 1
            apply_result =  __salt__['garage.post_uri_path']('/v2/ApplyClusterLayout', {'version': new_version})
            if apply_result.status_code == 200:
              ret["result"] = True
              ret["changes"][name] = "".join(apply_result.json()['message'])
            else:
              ret["result"] = False
              ret["comment"] = f"Something failed during apply cluster layout. {apply_result.status_code} {apply_result.json()}\n\nPlease check 'garage layout show' and 'garage layout history'"
          else:
            ret["result"] = True
            ret["comment"] = "Layout is already correct. You can manually verify it with 'garage layout show'"
        else:
          ret["result"] = False
          ret["comment"] = f"Error while updating the cluster layout: {post_result.status_code} {post_result.json()}"

  else:
    ret["result"] = False
    ret["comment"] = f"Error file fetching the current cluster layout {current_cluster_layout_result.status_code} {current_cluster_layout_result.json()}"

  return ret

def key_exists(name, key_id, secret_key, current_garage_keys):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}

  if key_id in current_garage_keys:
      ret["result"] = True
      ret["comment"] = f"Key {name}/{key_id} already exists"
  else:
    if __opts__["test"]:
      ret["comment"] = f"Creating key {name} with key_id {key_id}"
    else:
      key_data = { "accessKeyId": key_id, "name": name, "secretAccessKey": secret_key }
      import_key_result = __salt__['garage.post_uri_path']('/v2/ImportKey', key_data)
      if import_key_result.status_code == 200:
        ret["result"] = True
        ret["changes"][name] = f"Key {name}/{key_id} succesfully imported\n{import_key_result.json()}"
      else:
        ret["result"] = False
        ret["comment"] = f"Error importing the key: {import_key_result.status_code} {import_key_result.json()}"
  return ret

def key_absent(name, key_id):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}

  if __opts__["test"]:
    ret["comment"] = f"Deleting key {key_id}"
  else:
    delete_result = __salt__['garage.post_uri_path']('/v2/DeleteKey', params={'id': key_id})
    if delete_result.status_code == 200:
      ret["result"] = True
      ret["comment"] = f"Deleted key {key_id}"
      ret["changes"][key_id] = f"Deleted key {key_id}"
    else:
      ret["result"] = False
      ret["comment"] = f"Error deleting the key: {delete_result.status_code} {delete_result.json()}"

  return ret

def bucket_exists(name, config, current_garage_buckets=[]):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}
  changes = []

  bucket_info_result = __salt__['garage.get_uri_path']('/v2/GetBucketInfo', params={'globalAlias': name})
  if bucket_info_result.status_code == 500:
    ret["result"] = False
    ret["comment"] = f"Error while fetching bucket info for {name}: {bucket_info_result.status_code} {bucket_info_result.json()}"
    return ret
  elif bucket_info_result.status_code == 200:
    bucket_info = bucket_info_result.json()
  elif bucket_info_result.status_code == 404:
    new_bucket_data = {'globalAlias': name}
    if "local_alias" in config:
      new_bucket_data['localAlias'] = config['local_alias']
    bucket_create_result = __salt__['garage.post_uri_path']('/v2/CreateBucket', new_bucket_data)
    if bucket_create_result.status_code == 200:
      bucket_info = bucket_create_result.json()
      changes.append(f"Created Bucket {name}")
    else:
      ret["result"] = False
      ret["comment"] = f"Error while creating bucket {name}: {bucket_info_result.status_code} {bucket_info_result.json()}"
      return ret

  # TODO: update bucket fields

  if len(changes) > 0:
    ret['changes'][name] = changes
    ret['result'] = True
  return ret

def bucket_absent(name, bucket_id):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}
  if __opts__["test"]:
    ret["comment"] = f"Deleting bucket {bucket_id}"
  else:
    delete_result = __salt__['garage.post_uri_path']('/v2/DeleteBucket', params={'id': bucket_id})
    if delete_result.status_code == 200:
      ret["result"] = True
      ret["Comment"] = f"Buckets removed!"
      ret["changes"][bucket_id] = f"Deleted bucket"
    elif delete_result.status_code == 400:
      ret["result"] = False
      ret["comment"] = f"Bucket {bucket_id} is not empty!"
    elif delete_result.status_code == 400:
      ret["result"] = True
      ret["comment"] = f"Bucket {bucket_id} is already deleted"
    else:
      ret["result"] = False
      ret["comment"] = f"Error deleting the key: {delete_result.status_code} {delete_result.json()}"

  return ret
