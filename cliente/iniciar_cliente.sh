#!/bin/bash

mkdir -p /mnt/almacenamiento_dist
sleep 30

mount -t glusterfs gluster1:gvol /mnt/almacenamiento_dist
echo "GlusterFS montado en cliente:"
ls -la /mnt/almacenamiento_dist

exec python app.py
