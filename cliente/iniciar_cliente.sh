#!/bin/bash

mkdir -p /mnt/almacenamiento_dist
sleep 25

glusterd

mount -t glusterfs gluster1:gvol /mnt/almacenamiento_dist
exec python app.py