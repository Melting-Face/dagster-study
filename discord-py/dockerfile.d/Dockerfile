FROM python:3.13-slim

ENV APP_HOME=/app

WORKDIR $APP_HOME

COPY src/ $APP_HOME/

RUN pip install -r $APP_HOME/requirements.txt

ENTRYPOINT ["python", "app.py"]