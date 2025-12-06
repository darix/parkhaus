# Salt Formula for garage

## What can the formula do?

## installation

## Required salt master config:

```
file_roots:
  base:
    - {{ salt_base_dir }}/salt
    - {{ formulas_base_dir }}/parkhaus/salt

pillar_roots:
  base:
    - {{ salt_base_dir }}/pillar/
    - {{ formulas_base_dir }}/parkhaus/pillar/
## License
```
## cfgmgmt-template integration

if you are using our [cfgmgmt-template](https://github.com/darix/cfgmgmt-template) as a starting point the saltmaster you can simplify the setup with:

```
git submodule add https://github.com/darix/parkhaus formulas/parkhaus
ln -s /srv/cfgmgmt/formulas/parkhaus/config/enable_parkhaus.conf /etc/salt/master.d/
systemctl restart saltmaster
```

## Bootstrapping a cluster

Bootstrap works without errors but requires 3 runs from 0 to fullyconfigured

1. run: bring up basic garage instances
2. run: set up layout
3. run: set up rest of the configuration

Basically poor mans orchestration. Steps 2 and 3 are only run against the first node in the peerlist or the node designated with primary_node (see pillar example).

## Secrets (pre-generate keys) and ID

We should pre-generate `meta/node_key` and `meta/node_key.pub`.
You can do this via a Docker/Podman Garage container or a direct package install.

1. Start the Garage service.
2. Check the node ID with `garage node id` (or quietly: `garage node id -q`).
   You will later use it in the `garage:general:bootstrap_peers` pillar.
3. Base64-encode `meta/node_key` and `meta/node_key.pub`, nd then store those the node ID (at least the part before the @) and the base64 encoded node keys with your preferred encrypted pillar storage. The pillar example uses the gopass filter for it.

Reference: <https://garagehq.deuxfleurs.fr/documentation/quick-start/>

```bash
# example paths — adjust to your host
base64 -w 0 /var/lib/garage/meta/node_key
base64 -w 0 /var/lib/garage/meta/node_key.pub
```

And then store those the node ID (at least the part before the @) and the base64 encoded node keys with your preferred encrypted pillar storage. The pillar example uses the gopass filter for it.

## Add Garage keys

We can pre-geneate keys with
```
openssl rand -hex 12  # KEY_ID
openssl rand -hex 32  # SECRET_KEY
```
### Notes

* Garage not allow us to reuse KEY_ID after deletion.  You may reuse the same name/alias, but you must generate a new key_id.
* Garage keys must start with `GK`, we will add this as prefix in role sls.
  For secrets use only `openssl` generated string.

[AGPL-3.0-only](https://spdx.org/licenses/AGPL-3.0-only.html)
