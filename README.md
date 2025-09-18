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

[AGPL-3.0-only](https://spdx.org/licenses/AGPL-3.0-only.html)
