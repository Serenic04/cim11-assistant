FROM python:3.12-slim

WORKDIR /app

COPY app_streamlit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app_streamlit/app.py .

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
