#!/bin/bash
echo "hello" > hi.txt

HOST_IP=$(ip route show | awk '/default/ {print $3}')
export HOST_IP

echo "host is" "$HOST_IP" > out.txt

# Execute standard NiFi start script when finished
. /opt/nifi/scripts/start.sh

# ADD PYTHON SCRIPTS BELOW
