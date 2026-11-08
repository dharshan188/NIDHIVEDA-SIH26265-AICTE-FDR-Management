#!/bin/sh
# Stops whatever serve.py started: the processes listening on :8000 (uvicorn) and :5173 (vite).
for port in 8000 5173; do
  for pid in $(ss -ltnpH "sport = :$port" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do kill "$pid"; done
done
sleep 1
ss -ltnH '( sport = :8000 or sport = :5173 )' | grep -q . && echo "still listening" || echo "stopped"
