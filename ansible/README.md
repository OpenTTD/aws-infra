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


## IPv6 on OVH

OVH does provisioning of VPSes with DHCP for IPv4 and no IPv6 configured.
As we like IPv6, we have to do some manual work.
This is based on https://docs.ovh.com/gb/en/vps/configuring-ipv6/.

Disable cloud-init network provisioning (otherwise a reboot wipes our changes):
```
echo "network: {config: disabled}" | sudo tee /etc/cloud/cloud.cfg.d/98-disable-network-config.cfg
```

Create a configuration file that sets up IPv6:
```
cd /etc/network/interfaces.d/
sudo vi 60-ipv6
```

With `60-ipv6` having the content:
```
iface eth0 inet6 static
address <IPv6 of VM>
netmask 128
post-up /sbin/ip -6 route add <IPv6 gateway> dev eth0
post-up /sbin/ip -6 route add default via <IPv6 gateway> dev eth0
pre-down /sbin/ip -6 route del default via <IPv6 gateway> dev eth0
pre-down /sbin/ip -6 route del <IPv6 gateway> dev eth0
```

`IPv6 gateway` is defined like this:

- where `IPv6 of VM` is `2001:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:yyyy`
- `IPv6 gateway` is `2001:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:1`.

Validate IPv6 works:
```
sudo service networking restart
ping6 google.com
```

Reboot the machine to make sure IPv6 is still working.
