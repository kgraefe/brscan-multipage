# brscan-multipage

`brscan-multipage` hooks into the scan menu of your network-attached Brother
scanner or multifunction printer. As I use it in to feed my
[paperless-ngx](https://paperless-ngx.com/) instance, it offers functions for
document scanning only. The main feature is that it offers scanning multi-page
documents. It does that by offering 4 functions and keeping a stack of pages
internally:

1. Last page: Scan one page, add it to the stack and save the stack as PDF.
   This also serves for scanning single-page documents.
2. Multipage: Scan one page and add it to the stack.
3. Finish MP: Save the stack as PDF.
4. Abort MP: Clear the stack without saving. Discards all pages that have been
   scanned before.

Whenever the stack is saved as PDF it is also cleared.

The project is inspired by
[falkenber9/brother-scan](https://github.com/falkenber9/brother-scan). They
figured out the SNMP advertisments and UDP receptions.


## Supported devices
The protocol seems general enough so I assume that all scanner supported by
`brscan4` might work. However, I only own a `Brother DCP-7070DW` and this is
what I tested with.


## Usage

### Docker
Docker is the preferred way. The docker image is available at
[kgraefe/brscan-multipage](https://hub.docker.com/repository/docker/kgraefe/brscan-multipage/general).

It uses the following environment variables:
- `SCANNER_MODEL` (required): the scanner model as it is known by `brscan4`,
  e.g. `DCP-7070DW`
- `SCANNER_IP` (required): the IP address of the scanner
- `HOST_IP` (required): the IP address of the host running `brscan-multipage`
- `USERMAP_UID` and `USERMAP_GID` (optional, root containers only): user and
  group mapping to fix file permissions
- `TZ` (optional): the local timezone for proper timestamps in the filenames

It exposes the UDP port `54925` which *must be mapped to the very same port* on
the host. Otherwise the scanner won't reach the container when a menu entry is
selected.

The PDF documents are stored in `/output` which should be mapped as a volume to
wherever you want the documents to land, e.g. the paperless consume directory.

#### Docker CLI example
```sh
$ docker pull kgraefe/brscan-multipage:latest
$ docker run \
    --env "SCANNER_MODEL=DCP-7070DW" \
    --env "SCANNER_IP=192.168.178.40" \
    --env "HOST_IP=192.168.178.26" \
    --env "USERMAP_UID=$(id -u)" \
    --env "USERMAP_GID=$(id -g)" \
    --env "TZ=Europe/Berlin" \
    --publish "54925:54925/UDP" \
    --volume "$PWD/output:/output"
    kgraefe/brscan-multipage:latest
```

#### Docker compose example
```yml
--
version: "3.4"
services:
  brscan-multipage:
    image: kgraefe/brscan-multipage:latest
    restart: unless-stopped
    ports:
      - 54925:54925/udp
    environment:
      SCANNER_MODEL: DCP-7070DW
      SCANNER_IP: 192.168.178.40
      HOST_IP: 192.168.178.26
      USERMAP_UID: 1000
      USERMAP_GID: 1000
      TZ: Europe/Berlin
    volumes:
      - /wherever/paperless/consume:/output
    restart: unless-stopped
```

### Python environment
To run outside the container please refer to the help text of the script:
```sh
$ virtualenv venv
$ . ./venv/bin/activate
$ pip install -r requirements.txt
$ ./brscan_multipage.py --help
...
```


## Contributions
The project is tailored to my personal needs so I did not add too many options.
If you find you need something tweaked for your use case or to support your
scanner, please open a issue or (even better) a PR.
