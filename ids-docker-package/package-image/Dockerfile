FROM alpine:3.20

WORKDIR /opt/export

COPY . /opt/export/ids-docker-package

RUN rm -f /opt/export/ids-docker-package/config/ids-backend.env \
    && rm -f /opt/export/ids-docker-package/docker-compose.generated.yml \
    && rm -f /opt/export/ids-docker-package/docker-compose.registry.generated.yml \
    && rm -f /opt/export/ids-docker-package/docs/bootstrap-noise.latest.json \
    && rm -f /opt/export/ids-docker-package/docs/demo-console.latest.json \
    && rm -rf /opt/export/ids-docker-package/package-image \
    && rm -rf /opt/export/ids-docker-package/ids-data/quarantine \
    && rm -rf /opt/export/ids-docker-package/ids-data/reports \
    && rm -rf /opt/export/ids-docker-package/ids-data/uploads \
    && rm -rf /opt/export/ids-docker-package/ids-data/state \
    && rm -f /opt/export/ids-docker-package/ids-data/ids.db \
    && mkdir -p /opt/export/ids-docker-package/ids-data/quarantine \
    && mkdir -p /opt/export/ids-docker-package/ids-data/reports \
    && mkdir -p /opt/export/ids-docker-package/ids-data/uploads \
    && mkdir -p /opt/export/ids-docker-package/ids-data/state

COPY package-image/docker-entrypoint.sh /usr/local/bin/export-ids-package

RUN chmod +x /usr/local/bin/export-ids-package

ENTRYPOINT ["/usr/local/bin/export-ids-package"]
