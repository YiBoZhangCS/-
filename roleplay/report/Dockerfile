FROM ubuntu:24.04
# Runs the mounted Codex-bundled LibreOffice, never the host desktop installation.
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    libnss3 libfontconfig1 libdbus-1-3 libxinerama1 libxrender1 libsm6 libcups2 \
    libxml2 libxslt1.1 libglib2.0-0 libx11-xcb1 libxcb-shm0 libxcb-render0 \
    liblcms2-2 libxext6 libice6 libgomp1 libzstd1 libharfbuzz0b libfreetype6 \
    libpng16-16t64 libjpeg-turbo8 libexpat1 libcurl4t64
