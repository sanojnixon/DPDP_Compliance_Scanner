FROM python:3.11

WORKDIR /app

# System deps required by EasyOCR / OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install adb separately to prevent invalidating pip cache
RUN apt-get update && apt-get install -y --no-install-recommends adb && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
