FROM python:3.12-slim
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY trust-ledger-kernel /srv/trust-ledger-kernel
COPY backend /srv/backend
ENV TL_KERNEL_PATH=/srv/trust-ledger-kernel
CMD ["sh", "-c", "python scripts/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
