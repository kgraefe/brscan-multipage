FROM python:3.13-slim AS base
MAINTAINER Konrad Vité, kv@paktolos.net

FROM base AS builder

RUN apt-get update -q \
    && apt-get install -q -y --no-install-recommends \
        patch

ENV POETRY_VIRTUALENVS_CREATE=false

RUN pip install --root-user-action=ignore poetry==2.1.3

# install dependencies
COPY --from=projectroot \
    pyproject.toml \
    poetry.lock \
    containers/patches/pysnmp/0001-v1arch-set-next-bulk-_cmd-Implement-timeout-handling.patch \
    .

RUN poetry install --no-root --only main \
    && cd "$(pip show pysnmp | sed 's/^Location: //p;d')/pysnmp" \
    && patch -p2 < /0001-v1arch-set-next-bulk-_cmd-Implement-timeout-handling.patch

FROM base

# This must be mapped to ${HOST_IP}:54925
EXPOSE 54925/udp

RUN apt-get update -q \
    && apt-get install -q -y --no-install-recommends \
        sane-utils \
        gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ADD https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb .
RUN echo "027b73648722ac8c8eb1a9c419d284a6562cc763feac9740a2b75a683b092972  brscan4-0.4.11-1.amd64.deb" \
        | sha256sum -c \
    && dpkg --install brscan4-0.4.11-1.amd64.deb \
    && rm -rf brscan4-0.4.11-1.amd64.deb

# Remove all the other sane.d drivers to improve startup time
RUN echo "brother4" > /etc/sane.d/dll.conf

# Add user to run rootless
RUN set -eux \
    && addgroup --gid 1000 brscan \
    && useradd --uid 1000 --gid brscan --shell /bin/bash brscan

# Copy dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=projectroot \
    containers/entrypoint.sh \
    containers/run.sh \
    brscan_multipage.py \
    .

ENTRYPOINT ["/entrypoint.sh"]

CMD ["/run.sh"]
