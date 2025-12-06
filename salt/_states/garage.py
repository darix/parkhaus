import os
import logging
import requests
import re
import json
import functools
from salt.exceptions import SaltConfigurationError, SaltRenderError

log = logging.getLogger(__name__)

def _update_layout_data(current_node_data, new_node_data):
  new_node_list = []
  for node_data in current_node_data:
    new_node = {
      'id': node_data['id'],
    }
    for field in ['capacity', 'zone', 'tags']:
      new_node[field] = new_node_data.get(field, node_data.get(field))
    new_node_list.append(new_node)
  return new_node_list

def layout_assignment(name, capacity, zone, tags=[]):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}

  current_cluster_layout_result = __salt__['garage.get_uri_path']("/v2/GetClusterLayout")
  if current_cluster_layout_result.status_code == 200:
    current_cluster_layout = current_cluster_layout_result.json()

    all_correct = True
    if len(current_cluster_layout['roles']) > 0:
      for node in current_cluster_layout['roles']:
        if not(node.get('capacity') == capacity and node.get('zone') == zone and node.get('tags') == tags):
          all_correct = False
          break
    else:
      all_correct = False


    if all_correct:
      ret["result"] = True
      ret["comment"] = "Layout is already correct. You can manually verify it with 'garage layout show'"
    else:
      if __opts__["test"]:
        ret["comment"] = f"Layout needs updating"
      else:
        current_role_settings = current_cluster_layout['roles']
        if len(current_role_settings) == 0:
          gssr = __salt__['garage.get_uri_path']('/v2/GetClusterStatus')
          gss  = gssr.json()
          current_role_settings = [ {'id': node['id']} for node in gss['nodes']]

        new_data = {
          'roles': _update_layout_data(
            current_role_settings,
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

def _key_needs_assigning(new_key_data, existing_keys):
  for key_block in existing_keys:
    if  new_key_data['accessKeyId'] == key_block['accessKeyId'] and \
        new_key_data['permissions']['read']  == key_block['permissions']['read'] and \
        new_key_data['permissions']['write'] == key_block['permissions']['write'] and \
        new_key_data['permissions']['owner'] == key_block['permissions']['owner']:
        return False
  return True

def _bucket_info_result_from(bucket_name):
  bucket_result = __salt__['garage.get_uri_path']("/v2/GetBucketInfo", {'globalAlias': bucket_name})
  if bucket_result.status_code in [200, 404]:
    return bucket_result
  else:
    raise SaltConfigurationError(f"Can not bucket information for {bucket_name} {bucket_result.status_code}: {bucket_result.json()}")

def bucket_exists(name, current_garage_buckets=[]):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}
  changes = []
  bucket_info = {}

  bucket_info_result = _bucket_info_result_from(name)
  if bucket_info_result.status_code == 500:
    ret["result"] = False
    ret["comment"] = f"Error while fetching bucket info for {name}: {bucket_info_result.status_code} {bucket_info_result.json()}"
    return ret
  elif bucket_info_result.status_code == 200:
    ret["result"] = True
    ret["comment"] = f"Bucket {name} already exists"
  elif bucket_info_result.status_code == 404:
    new_bucket_data = {'globalAlias': name}

    bucket_create_result = __salt__['garage.post_uri_path']('/v2/CreateBucket', new_bucket_data)
    if bucket_create_result.status_code == 200:
      bucket_info = bucket_create_result.json()
      ret['result'] = True
      ret['changes'][name] = changes

    else:
      ret["result"] = False
      ret["comment"] = f"Error while creating bucket {name}: {bucket_info_result.status_code} {bucket_info_result.json()}"
      return ret

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
    elif delete_result.status_code == 404:
      ret["result"] = True
      ret["comment"] = f"Bucket {bucket_id} is already deleted"
    else:
      ret["result"] = False
      ret["comment"] = f"Error deleting the key: {delete_result.status_code} {delete_result.json()}"
  return ret

def bucket_set_config(name, bucket_name, bucket_config):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}
  bucket_info_result = _bucket_info_result_from(bucket_name)
  bucket_info = bucket_info_result.json()
  bucket_id = bucket_info['id']
  if __opts__["test"]:
    ret["comment"] = f"Updating config on {bucket_id}"
  else:
    if functools.reduce(lambda a,b: a & b, [(bucket_info[key] == bucket_config[key]) for key in bucket_config.keys()]):
      ret["result"] = True
      ret["comment"] = f"Bucket config already correct"
    else:
      set_config_result = __salt__['garage.post_uri_path']('/v2/UpdateBucket', post_data=bucket_config, params={'id': bucket_id})
      if set_config_result.status_code == 200:
        ret["result"] = True
        ret["comment"] = f"Bucket config updated"
        ret["changes"] = bucket_config
      elif set_config_result.status_code == 404:
        ret["result"] = False
        ret["comment"] = f"Bucket {bucket_id} does not exist"
      else:
        ret["result"] = False
        ret["comment"] = f"Error updating the bucket config: {set_config_result.status_code} {set_config_result.json()}"
  return ret


def bucket_key_assignment_present(name, bucket_name, key_name, permissions):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}
  bucket_info_result = _bucket_info_result_from(bucket_name)
  bucket_info = bucket_info_result.json()

  key_result    = __salt__['garage.get_uri_path']("/v2/GetKeyInfo",    {'search': key_name})
  if key_result.status_code == 200:
    krj = key_result.json()
    new_data = {
      'bucketId': bucket_info['id'],
      'accessKeyId': krj['accessKeyId'],
      'permissions': {
        'read':  permissions.get('read', False),
        'write': permissions.get('write', False),
        'owner': permissions.get('owner', False),
      },
    }

    if _key_needs_assigning(new_data, bucket_info['keys']):
      update_result = __salt__['garage.post_uri_path']('/v2/AllowBucketKey', post_data=new_data)
      if update_result.status_code == 200:
        ret["result"] = True
        ret["changes"][name] = f"Assigned key {key_name} to {name}"
      else:
        ret["result"] = False
        ret["comment"] = f"Error while assigning a key {update_result.status_code}: {update_result.json()}"
    else:
      ret["result"] = True
      ret["comment"] = f"Key already properly assigned"
  else:
    ret["result"] = False
    ret["comment"] = f"Error while fetching key info {key_result.status_code}: {key_result.json()}"
  return ret

def bucket_key_assignment_absent(name, key_name, bucket_id, accessKeyId, permissions):
  ret = {'name': name, 'result': None, 'changes': {}, 'comment': ""}

  new_data = {
    'bucketId':    bucket_id,
    'accessKeyId': accessKeyId,
    'permissions': permissions,
  }

  update_result = __salt__['garage.post_uri_path']('/v2/DenyBucketKey', post_data=new_data)

  if update_result.status_code == 200:
    ret["result"] = True
    ret["changes"][name] = f"Dropped assigned key {key_name} to {bucket_id}"
  else:
    ret["result"] = False
    ret["comment"] = f"Error while drop a key assignment {update_result.status_code}: {update_result.json()}"

  return ret

