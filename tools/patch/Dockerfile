# GNU ARM bare-metal toolchain + python3-lzo, for building NL4 OS patches (tools/patch/build.sh).
FROM debian:12-slim
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      gcc-arm-none-eabi binutils-arm-none-eabi libnewlib-arm-none-eabi make python3 python3-lzo \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /w
