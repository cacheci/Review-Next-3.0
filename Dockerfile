FROM python:3.12-slim

RUN apt-get update && apt-get install -y git

WORKDIR /app/

RUN git clone https://github.com/Rovniced/Review-Next.git /app

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'git pull' >> /app/start.sh && \
    echo 'pip install -r requirements.txt' >> /app/start.sh && \
    echo 'python main.py' >> /app/start.sh && \
    chmod +x /app/start.sh

CMD ["/app/start.sh"]