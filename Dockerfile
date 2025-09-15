# Use slim Python base image
FROM python:3.13-slim-trixie

# Set working directory
WORKDIR /ps2mcs

# Copy dependency list and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy selected root files
COPY LICENSE README.md progress.py ps2mcs.py sync_target.py ./

# Copy mapping package files
COPY mapping/__init__.py mapping/flat.py mapping/

ENTRYPOINT ["python", "ps2mcs.py"]
CMD ["-h"]
