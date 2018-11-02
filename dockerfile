FROM python:3
WORKDIR /app
ADD . /app
RUN pip install --trusted-host pypi.python.org -r requirements.txt
EXPOSE 80
ENV NAME mac_Addresses_app
CMD ["python","run.py","runserver","-h","0.0.0.0"]
