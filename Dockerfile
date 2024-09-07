FROM joyzoursky/python-chromedriver:latest

ENV PYTHONUNBUFFERED 1

WORKDIR /app


RUN apt-get update && \
    apt-get install -y --no-install-recommends netcat && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY pyproject.toml poetry.lock ./
RUN python3 -m pip install poetry && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-dev

COPY . ./

CMD poetry run python -m app
