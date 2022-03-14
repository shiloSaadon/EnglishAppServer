FROM python:3.10-slim-buster

COPY ./sounds ./sounds
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY ./src ./src


WORKDIR .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
