import os
import logging
import requests
import re
import json
from salt.exceptions import SaltConfigurationError, SaltRenderError

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

def get_uri_path(uri_path, params={}):
    full_url = _get_full_url(uri_path)
    result = requests.get(full_url, headers=_auth_header(), params=params)
    log.error(f"get_uri_path: reponse {result.status_code} json: {result.json()}")
    return result

def post_uri_path(uri_path, post_data={}, params={}, content_type='application/json'):
    full_url = _get_full_url(uri_path)
    log.error(f"post_data: {post_data}")
    json_post_data = json.dumps(post_data, indent=2)
    headers = _auth_header({'content-type': content_type})
    result = requests.post(full_url, headers=headers, data=json_post_data, params=params)
    log.error(f"post_uri_path: reponse {result.status_code} json: {result.json()}")
    return result

def list_keys():
  key_list_result = get_uri_path('/v2/ListKeys')
  if key_list_result.status_code == 200:
    return key_list_result.json()
  else:
    raise SaltConfigurationError(f"Can not fetch existing Keys: {key_list_result.status_code} {key_list_result.json()}")

def list_buckets():
  bucket_list_result = get_uri_path('/v2/ListBuckets')
  if bucket_list_result.status_code == 200:
    return bucket_list_result.json()
  else:
    raise SaltConfigurationError(f"Can not fetch existing Keys: {key_lbucket_list_resultist_result.status_code} {bucket_list_result.json()}")