FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# ✅ Copy all source files including static folder
COPY . .

EXPOSE 5001

CMD ["python", "app.py"]
