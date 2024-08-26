#!/usr/bin/env sh

if [ -z "$API_ID" ]; then
    echo "environment variable API_ID not found" 1>&2
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "environment variable API_HASH not found" 1>&2
    exit 1
fi


if [ -z "$BOT_TOKEN" ]; then
    echo "environment variable BOT_TOKEN not found" 1>&2
    exit 1
fi


if [ -z "$ADMIN_CHAT" ]; then
    echo "environment variable ADMIN_CHAT not found" 1>&2
    exit 1
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    echo "environment variable ENCRYPTION_KEY not found" 1>&2
    exit 1
fi


if [ ! -f "$(pwd)/mapping.bin" ]; then
    touch "$(pwd)/mapping.bin"
fi


if [ ! -f "$(pwd)/.aiotdlib" ]; then
    mkdir "$(pwd)/.aiotdlib"
fi


docker build -f .deploy/Dockerfile -t shroombot .

docker stop shroombot || true
docker rm shroombot || true

docker run -d \
    --restart always \
    -e API_ID="${API_ID}" \
    -e API_HASH="${API_HASH}" \
    -e BOT_TOKEN="${BOT_TOKEN}" \
    -e ADMIN_CHAT="${ADMIN_CHAT}" \
    -e ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
    -v "$(pwd)/mapping.bin:/mapping.bin" \
    -v "$(pwd)/.aiotdlib:/.aiotdlib" \
    --name shroombot shroombot \
    /mapping.bin /.aiotdlib
