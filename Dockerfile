# Docker File
# SOURCE: https://www.youtube.com/watch?v=DxET43rUkig

# Define global args
ARG FUNCTION_DIR="/home/app/"
ARG RUNTIME_VERSION="3.9"
ARG DISTRO_VERSION="3.14"


# Stage 1 - bundle base image + runtime
# Grab a fresh copy of the image and install GCC
FROM python:${RUNTIME_VERSION}-alpine${DISTRO_VERSION} AS python-alpine
# Install GCC (Alpine uses musl but we compile and link dependencies with GCC)
RUN apk add --no-cache \
    libstdc++


# Stage 2 - build function and dependencies
FROM python-alpine AS build-image
# Install aws-lambda-cpp build dependencies
RUN apk add --no-cache \
    build-base \
    libtool \
    autoconf \
    automake \
    libexecinfo-dev \
    make \
    cmake \
    libcurl 
# Include global args in this stage of the build
ARG FUNCTION_DIR
ARG RUNTIME_VERSION
# Create function directory
RUN mkdir -p ${FUNCTION_DIR}

# Stage 3 - Add app related dependencies
FROM python-alpine as build-image2
ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
# Copy in the built dependencies
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}
# Copy over and install requirements
RUN apk update \
    && apk add gcc python3-dev musl-dev \
    && apk add jpeg-dev zlib-dev libjpeg-turbo-dev \ 
    && apk add libffi-dev
COPY requirements.txt .
RUN python${RUNTIME_VERSION} -m pip install -r requirements.txt --target ${FUNCTION_DIR}


# Stage 4 - final runtime image
# Grab a fresh copy of the Python image
FROM python-alpine
ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
# Copy in the built dependencies
COPY --from=build-image2 ${FUNCTION_DIR} ${FUNCTION_DIR}
RUN apk add jpeg-dev zlib-dev libjpeg-turbo-dev \
    && apk add chromium chromium-chromedriver

# Copy handler function
COPY src ${FUNCTION_DIR}
CMD [ "python3", "LegislativeRequest.py" ]