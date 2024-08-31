#!/usr/bin/env sh

docker build -f .deploy/Dockerfile -t shroombot .

# docker stop shroombot || true
# docker rm shroombot || true

# docker run -d \
#     --restart always \
#     -e API_ID="${API_ID}" \
#     -e API_HASH="${API_HASH}" \
#     -e BOT_TOKEN="${BOT_TOKEN}" \
#     -e ADMIN_CHAT="${ADMIN_CHAT}" \
#     -e ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
#     -v "$(pwd)/mapping.bin:/mapping.bin" \
#     -v "$(pwd)/.aiotdlib:/.aiotdlib" \
#     --name shroombot shroombot \
#     /mapping.bin /.aiotdlib
