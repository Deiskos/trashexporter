FROM python:3.8-slim-bullseye AS base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base as python-deps

RUN pip install pipenv
RUN apt-get update && apt-get install -y --no-install-recommends gcc

COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy


FROM base as runtime
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"
WORKDIR /work
COPY . /work

CMD [ "python3", "trashexporter.py" ]
