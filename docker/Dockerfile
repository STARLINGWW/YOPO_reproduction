# Use Docker's bundled frontend; no separate docker/dockerfile image is needed.
ARG CUDA_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu22.04
FROM ubuntu:22.04 AS ros-core
ARG DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 ROS_DISTRO=humble \
    ROS_DOMAIN_ID=42 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    ROS_LOG_DIR=/workspace/artifacts/ros2_logs
RUN --mount=type=cache,id=yopo-jammy-apt,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=yopo-jammy-lists,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
    ca-certificates curl gnupg \
    build-essential cmake git pkg-config python3 python3-dev python3-pip python3-venv \
    libeigen3-dev libyaml-cpp-dev libboost-thread-dev libboost-filesystem-dev libboost-system-dev libgl1 libglib2.0-0
COPY docker/ros-archive-keyring.gpg /usr/share/keyrings/ros-archive-keyring.gpg
RUN --mount=type=cache,id=yopo-jammy-apt,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=yopo-jammy-lists,target=/var/lib/apt/lists,sharing=locked \
    printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main' \
       > /etc/apt/sources.list.d/ros2.list \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
       ros-humble-ros-base ros-humble-rmw-fastrtps-cpp ros-humble-sensor-msgs \
       ros-humble-nav-msgs ros-humble-trajectory-msgs ros-humble-tf2-ros \
       ros-humble-rosbag2 ros-humble-rosbag2-storage-mcap ros-humble-launch-testing \
       ros-humble-ament-cmake ros-humble-rosidl-default-generators \
       python3-colcon-common-extensions python3-rosdep python3-pytest python3-numpy
RUN useradd --create-home --uid 1000 --shell /bin/bash yopo \
    && mkdir -p /data && chown yopo:yopo /data
COPY docker/entrypoint.sh /usr/local/bin/yopo-entrypoint
RUN chmod 755 /usr/local/bin/yopo-entrypoint
WORKDIR /workspace
USER yopo
ENTRYPOINT ["/usr/local/bin/yopo-entrypoint"]
CMD ["bash"]

FROM ros-core AS baseline-cpp
USER root
RUN --mount=type=cache,id=yopo-jammy-apt,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=yopo-jammy-lists,target=/var/lib/apt/lists,sharing=locked \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
       libpcl-dev libnlopt-dev libnlopt-cxx-dev libopencv-dev \
       ros-humble-cv-bridge ros-humble-image-transport ros-humble-message-filters \
       ros-humble-visualization-msgs ros-humble-pcl-conversions
USER yopo

FROM ${CUDA_IMAGE} AS cuda-toolkit

FROM ros-core AS train
USER root
# ROS2 CPU tooling does not depend on the large CUDA image. The training target
# includes its complete versioned Toolkit; PyTorch supplies its CUDA runtime.
COPY --from=cuda-toolkit /usr/local/cuda-12.8 /usr/local/cuda-12.8
ENV CUDA_HOME=/usr/local/cuda-12.8 \
    PATH=/usr/local/cuda-12.8/bin:${PATH} \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --timeout 120 --retries 10 pip==25.2
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --timeout 120 --retries 10 --resume-retries 10 \
    torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
COPY docker/requirements-training.txt /tmp/requirements-training.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --timeout 120 --retries 10 --resume-retries 10 -r /tmp/requirements-training.txt && python3 -m pip check
USER yopo
