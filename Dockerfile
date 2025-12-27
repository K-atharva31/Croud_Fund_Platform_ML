FROM python:3.9-slim

WORKDIR /app

COPY . .

# Install build tools and dependencies
RUN apt-get update && apt-get install -y gcc build-essential libffi-dev \
    && python -m pip install --upgrade pip \
    && pip install --no-cache-dir Flask==2.2.5 Flask-PyMongo==2.3.0 Flask-Cors==3.0.10 Werkzeug==2.2.3 python-dotenv==1.0.0 pymongo==4.3.3 \
    && apt-get remove -y gcc build-essential libffi-dev \
    && apt-get autoremove -y \
    && apt-get clean

EXPOSE 5000

CMD ["python", "main.py"]
