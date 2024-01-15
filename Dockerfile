# Use a base image with Python installed
FROM python:3.12-alpine

WORKDIR /app

RUN apk update && apk add --no-cache gcc python3-dev libev-dev musl-dev

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY plex_media_reanalyzer.py .

ENTRYPOINT [ "python3", "plex_media_reanalyzer.py"]