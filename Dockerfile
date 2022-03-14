FROM python:3.10-slim-buster

COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY ./src ./src

WORKDIR ./src

CMD ["uvicorn", "main:app", "-h", "0.0.0.0", "-p", "8000"]
