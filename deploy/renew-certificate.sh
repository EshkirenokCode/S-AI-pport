#!/bin/sh
set -eu
docker exec mayak-proxy /opt/certbot/bin/certbot renew \
  --cert-name saipport.gulevskii.dev --non-interactive \
  --deploy-hook 'nginx -t && nginx -s reload'
