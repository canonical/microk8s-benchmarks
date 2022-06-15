#!/bin/bash

## set $VS_USER, $VS_PASS, $VS_CONTROLLER for non-interactive install.

set -eu
if [ -z ${VS_USER+1} ]; then
  read -p "vSphere username: " vs_user
else
  echo "Using ENV setting for username"
  vs_user=$VS_USER
fi
if [ -z ${VS_PASS+1} ]; then
  read -p "vSphere password: " vs_pass
else
  echo "Using ENV setting for password"
  vs_pass=$VS_PASS
fi
if [ -z ${VS_CONTROLLER+1} ]; then
  read -p "name of controller to add: " vs_controller
else 
  echo "using ENV setting for controller name"
  vs_controller=$VS_CONTROLLER
fi

echo "Installing Juju..."
sudo snap install juju  --classic
sudo snap install juju-wait --classic

echo "Adding vSphere cloud"
echo >> ~/vs.yaml "clouds:
   vsphere:
     type: vsphere
     auth-types: [userpass]
     endpoint: 10.246.152.100
     regions:
       Boston:
         endpoint: 10.246.152.100"
juju add-cloud vsphere ~/vs.yaml
rm ~/vs.yaml

echo "Adding credential"
echo > ~/vs-cred.yaml "credentials:
    vsphere:
      k8s-crew:
        auth-type: userpass
        password: $vs_pass
        user: $vs_user
        vmfolder: k8s-crew-root"
juju add-credential vsphere -f ~/vs-cred.yaml --client
rm ~/vs-cred.yaml

echo "Bootstrapping cloud..."
juju bootstrap \
  --credential k8s-crew \
  --debug \
  --model-default automatically-retry-hooks=false \
  --model-default 'logging-config=<root>=DEBUG' \
  --model-default datastore=vsanDatastore \
  --model-default primary-network=VLAN_2764 \
  --config caas-image-repo=rocks.canonical.com/cdk/jujusolutions \
  --bootstrap-image="juju-ci-root/templates/focal-test-template" \
  --bootstrap-series=focal \
  --bootstrap-constraints "arch=amd64" \
  vsphere/Boston $vs_controller
sleep 5s

echo "juju controller bootstrapped - setting model defaults"
juju model-defaults juju-http-proxy=http://squid.internal:3128
juju model-defaults juju-https-proxy=http://squid.internal:3128
juju model-defaults apt-http-proxy=http://squid.internal:3128
juju model-defaults apt-https-proxy=http://squid.internal:3128
juju model-defaults snap-http-proxy=http://squid.internal:3128
juju model-defaults snap-https-proxy=http://squid.internal:3128
juju model-defaults apt-no-proxy=localhost,127.0.0.1,0.0.0.0,ppa.launchpad.net,launchpad.net,10.0.8.0/24
juju model-defaults juju-no-proxy=localhost,127.0.0.1,0.0.0.0,ppa.launchpad.net,launchpad.net,10.0.8.0/24