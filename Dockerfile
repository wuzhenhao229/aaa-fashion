FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN mkdir -p /app/gallery
ENV PORT=7860
EXPOSE 7860
CMD ["python3", "server.py"]
