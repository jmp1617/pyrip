FROM alpine

RUN apk add python3

ADD pyrip.py /
ADD configuration.py /