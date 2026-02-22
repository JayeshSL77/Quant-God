#!/bin/bash
set -e

echo "📦 Packaging Source Code for Server-Side Build..."

# Clean previous
rm -rf inwezt_source_pkg.zip

# Zip everything needed for build
zip -r inwezt_source_pkg.zip \
    inwezt_frontend \
    backend \
    deployment \
    run.py \
    requirements.txt \
    .env.example

echo "✅ Source package created: inwezt_source_pkg.zip"
