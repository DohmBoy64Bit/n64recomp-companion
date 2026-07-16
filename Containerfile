FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG N64RECOMP_REF=ffb39cdad1da5de07eaaa48bd1db4a89a7986771
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/opt/decomp-tools/bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       git \
       cmake \
       ninja-build \
       clang \
       build-essential \
       python3 \
       python3-pip \
       python3-venv \
       pkg-config \
       binutils-mips-linux-gnu \
       gcc-mips-linux-gnu \
       g++-mips-linux-gnu \
       curl \
       jq \
       ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/decomp-tools \
    && /opt/decomp-tools/bin/python -m pip install 'pip==25.1.1' \
    && /opt/decomp-tools/bin/python -m pip install 'splat64[mips]==0.41.0' 'uv==0.10.0'

RUN git clone --recurse-submodules https://github.com/N64Recomp/N64Recomp.git /opt/n64recomp \
    && cd /opt/n64recomp \
    && git checkout --detach "${N64RECOMP_REF}" \
    && test "$(git rev-parse HEAD)" = "${N64RECOMP_REF}" \
    && git submodule update --init --recursive \
    && cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --parallel "$(nproc)" \
    && ln -sf /opt/n64recomp/build/N64Recomp /usr/local/bin/N64Recomp \
    && if [ -x /opt/n64recomp/build/RSPRecomp ]; then ln -sf /opt/n64recomp/build/RSPRecomp /usr/local/bin/RSPRecomp; fi \
    && if [ -x /opt/n64recomp/build/RecompModTool ]; then ln -sf /opt/n64recomp/build/RecompModTool /usr/local/bin/RecompModTool; fi

WORKDIR /opt/n64recomp-companion
COPY pyproject.toml README.md LICENSE requirements-decomp.txt ./
COPY n64recomp_kit ./n64recomp_kit
RUN python3 -m pip install --break-system-packages .

WORKDIR /work
CMD ["bash"]
