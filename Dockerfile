FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV PORT=8000
ENV STUDYCIRCLE_DATA=/data
EXPOSE 8000
CMD ["python", "server.py"]
