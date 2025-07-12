#!/bin/bash

mkdir -p /app/almacenamiento_dist
sleep 30

mount -t glusterfs gluster1:gvol /app/almacenamiento_dist
echo "GlusterFS montado en cliente:"
ls -la /app/almacenamiento_dist

exec python app.py
