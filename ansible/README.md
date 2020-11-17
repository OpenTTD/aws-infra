# Extremely basic instructions for using ansible

Requirements:
* Public ssh keys to authorized_keys of the debian user on all content servers

Then run:

```
ansible-galaxy install -r requirements.yml
ansible-playbook --user debian --inventory inventory --diff content-servers.yml
```

Due to a quirk of configuration, the staging hosts happen to be the same hosts as the production hosts
If this ever changes, remove the "staging" specific stuff from the playbook and add the staging hosts (and variables) to the inventory.
