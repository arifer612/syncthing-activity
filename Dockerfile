ARG PYTHON_VER=3
ARG ALPINE_VER=""

FROM python:${PYTHON_VER}-alpine${ALPINE_VER}

LABEL org.label-schema.name="arifer612/syncthing-activity"
LABEL org.label-schema.version="1.0.0"
LABEL org.label-scheme.docker.cmd="docker run -d -v ~/scripts/:/scripts:rw -e \"SYNCTHING_URL=http://localhost:8384\" -e \"SYNCTHING_API=xxxx\" arifer612/syncthing-activity"
LABEL version="latest"

ENV SYNCTHING_URL="http://localhost:8384"
ENV SYNCTHING_API=""
ENV API_TYPE="ItemFinished"
ENV SCRIPT="'"
ENV ARGUMENTS=""

COPY . /opt/app
WORKDIR /opt/app
RUN pip install -r requirements.txt
RUN install -m 755 syncthing-activity.py /usr/bin/syncthing-activity

WORKDIR /scripts
ENTRYPOINT syncthing-activity ${API_TYPE} --script ${SCRIPT} ${ARGUMENTS}
