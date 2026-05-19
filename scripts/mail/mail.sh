#!/usr/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")"; pwd -P )
cd "$parent_path"

sudo apt update
sudo apt install -y postfix ca-certificates opendkim opendkim-tools mailutils

# postfix config
sudo cp main.cf /etc/postfix/main.cf

# opendkim genkey
sudo mkdir -p /etc/opendkim/keys/photo-scan.store
sudo opendkim-genkey -s mail -b 1024 -d photo-scan.store -D /etc/opendkim/keys/photo-scan.store -v
sudo chown -R opendkim:opendkim /etc/opendkim/keys

# opendkim config
sudo cp opendkim.conf /etc/opendkim.conf
sudo cp key.table /etc/opendkim/KeyTable
sudo cp signing.table /etc/opendkim/SigningTable
sudo cp trusted.hosts /etc/opendkim/TrustedHosts

# restart services
sudo systemctl enable opendkim postfix
sudo systemctl restart opendkim postfix

echo "Set DKIM1 DNS record:"
cat /etc/opendkim/keys/photo-scan.store/mail.txt

sudo newaliases
sudo systemctl restart postfix