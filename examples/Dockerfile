FROM python:2.7.8

ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    libxml2-dev libxslt-dev python-dev  \
    libyaml-dev \
    graphviz

COPY requirements.txt requirements.txt

RUN pip install -U plop gprof2dot ipython
RUN pip install -r requirements.txt

RUN mkdir /app-entrypoint.d

#COPY app-entrypoint.sh /

#ENTRYPOINT ["/app-entrypoint.sh"]

ENTRYPOINT ["/bin/bash", "-c"]

#CMD ["echo 'hello'"]
