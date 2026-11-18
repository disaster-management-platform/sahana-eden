FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/web2py
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.lock
COPY source/web2py /opt/web2py
RUN mv applications/eden /opt/eden \
    && for directory in databases sessions errors uploads cache; do \
      rm -rf /opt/eden/$directory; \
      ln -s /data/$directory /opt/eden/$directory; \
    done \
    && ln -s /config/000_config.py /opt/eden/models/000_config.py
COPY templates/platform /opt/eden/modules/templates/platform
COPY entrypoint.sh /usr/local/bin/eden-entrypoint
EXPOSE 8000
ENTRYPOINT ["sh", "/usr/local/bin/eden-entrypoint"]
