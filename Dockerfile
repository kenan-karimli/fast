FROM python

COPY . .

RUN ["pip","install", "requirements.txt"]

EXPOSE 8000

CMD ["uvicorn","main:app", "--host", "0.0.0.0", "--port", "8000"]

