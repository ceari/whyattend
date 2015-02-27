FROM ubuntu

RUN apt-get update && apt-get install -y python-setuptools python-psycopg2
RUN easy_install pip

ADD requirements.txt /src/requirements.txt
RUN cd /src; pip install -r requirements.txt; pip install tornado

ADD whyattend /src/whyattend
ADD runtornado.py /src/runtornado.py
ADD docker_config.py /src/local_config.py
ADD alembic_docker.ini /src/alembic.ini
ADD initdb.py /src/initdb.py

EXPOSE 5000

WORKDIR /src
CMD ["python", "./initdb.py"]
CMD ["python", "./runtornado.py"]
