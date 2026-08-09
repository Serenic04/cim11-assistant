FROM python:3.12-slim

WORKDIR /app

COPY model_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model_api/app ./app

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
