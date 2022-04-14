ARG PYTHON_VER=3
ARG ALPINE_VER=""

FROM python:${PYTHON_VER}-alpine${ALPINE_VER}

ARG SCRIPT_VER

LABEL org.label-schema.name="arifer612/syncthing-activity"
LABEL org.label-schema.version=${SCRIPT_VER}
LABEL org.label-scheme.docker.cmd="docker run -d -v ~/scripts/:/scripts:rw -e \"SYNCTHING_URL=http://localhost:8384\" -e \"SYNCTHING_API=xxxx\" arifer612/syncthing-activity"

ENV SYNCTHING_URL="http://localhost:8384"
ENV SYNCTHING_API=""
ENV API_TYPE="ItemFinished"
ENV SCRIPT=""
ENV ARGUMENTS=""

# https://stackoverflow.com/a/24183941
ENV PYTHONUNBUFFERED=1

COPY . /opt/app
WORKDIR /opt/app
RUN pip install -r requirements.txt
RUN chmod 755 syncthing-activity.py

VOLUME /scripts
WORKDIR /scripts
RUN [[ -f /scripts/requirements.txt ]] && pip install -r \
    /scripts/requirements.txt || exit 0
ENTRYPOINT /opt/app/syncthing-activity.py --event ${API_TYPE} --script ${SCRIPT} ${ARGUMENTS}
