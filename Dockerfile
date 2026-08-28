FROM python:3.14-slim

WORKDIR /app

# Dependencies first. This layer is slow to build and almost never changes,
# so Docker caches it and skips it on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code second. This changes constantly, so it goes last — only this
# layer rebuilds when you edit a script.
COPY *.py ./
COPY targets_known.csv targets_control.csv ./

# lightkurve caches downloads under the home directory; point that at a
# folder we can mount, so the cache survives between runs.
ENV HOME=/cache

CMD ["python", "run_all.py"]
