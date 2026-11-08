"""Start a separate SeaweedFS instance; keep tl-gap-s3 untouched."""
import os
import secrets
import subprocess

env = {**os.environ, "S3_ACCESS_KEY": secrets.token_hex(12), "S3_SECRET_KEY": secrets.token_hex(32)}
command = ["docker", "run", "-d", "--name", "tl-baseline-s3", "-p", "127.0.0.1:8334:8333",
           "-e", "S3_ACCESS_KEY", "-e", "S3_SECRET_KEY", "--entrypoint", "/bin/sh", "chrislusf/seaweedfs:3.97", "-c",
           '''printf '{"identities":[{"name":"tl","credentials":[{"accessKey":"%s","secretKey":"%s"}],"actions":["Admin","Read","Write","List","Tagging"]}]}' "$S3_ACCESS_KEY" "$S3_SECRET_KEY" > /tmp/s3.json && exec /entrypoint.sh server -s3 -s3.port=8333 -s3.config=/tmp/s3.json -dir=/data -master.volumeSizeLimitMB=32 -master.volumePreallocate=false -volume.max=8 -volume.minFreeSpace=64MiB''']
print("docker run -d --name tl-baseline-s3 -p 127.0.0.1:8334:8333 -e S3_ACCESS_KEY -e S3_SECRET_KEY --entrypoint /bin/sh chrislusf/seaweedfs:3.97 -c '<create config from environment; start S3>'", flush=True)
subprocess.run(command, env=env, check=True)
