FROM debian@sha256:f324c7ff54321e8d9c588493a20244965938ce0aa50bbd1022d38010e9ffc4b1
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential bison flex gawk git curl ca-certificates xz-utils bzip2 patch python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
