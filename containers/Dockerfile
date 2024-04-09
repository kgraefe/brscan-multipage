FROM python:3.8-slim
MAINTAINER Konrad Gräfe, kg@paktolos.net

# This must be mapped to ${HOST_IP}:54925
EXPOSE 54925/udp

RUN apt-get update -q \
    && apt-get install -q -y sane-utils imagemagick gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ADD https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb .
RUN echo "027b73648722ac8c8eb1a9c419d284a6562cc763feac9740a2b75a683b092972  brscan4-0.4.11-1.amd64.deb" \
        | sha256sum -c \
    && dpkg --install brscan4-0.4.11-1.amd64.deb

# Relax ImageMagick PDF security. See https://stackoverflow.com/a/59193253
RUN sed -i '/rights="none" pattern="PDF"/d' /etc/ImageMagick-6/policy.xml

# Remove all the other sane.d drivers to improve startup time
RUN echo "brother4" > /etc/sane.d/dll.conf \
    && rm /etc/sane.d/dll.d/*

# Add user to run rootless
RUN set -eux \
    && addgroup --gid 1000 brscan \
    && useradd --uid 1000 --gid brscan --shell /bin/bash brscan
    
WORKDIR /brscan-multipage
COPY --from=projectroot requirements.txt .
RUN pip install -r requirements.txt

COPY --from=projectroot \
    containers/entrypoint.sh \
    containers/run.sh \
    brscan_multipage.py \
    .

ENTRYPOINT ["./entrypoint.sh"]

CMD ["./run.sh"]
