#!/usr/bin/env bash
set -e
curl -s -X POST http://localhost:8001/orders \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"c-001","amount":120000,"items":[{"product_id":"p-001","quantity":2}]}' | jq
