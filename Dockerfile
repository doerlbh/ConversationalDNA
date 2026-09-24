FROM python:3.11-slim
RUN useradd --create-home --uid 1000 dna
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=dna:dna app /app/app
COPY --chown=dna:dna codes/representation.py codes/retrieval.py /app/codes/
USER dna
ENV DNA_DATABASE=/app/app/demo.sqlite
EXPOSE 7860
CMD ["python", "app/server.py", "--host", "0.0.0.0", "--port", "7860"]
