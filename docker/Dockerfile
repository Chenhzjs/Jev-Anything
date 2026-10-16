FROM rust:1.88-bookworm AS builder

ARG GUI2TUI_COMMIT=7bf1116119775d5038376b18d077133e3f6f8ea2
WORKDIR /src
RUN git clone https://github.com/Chenhzjs/GUI2TUI.git . \
    && git checkout "$GUI2TUI_COMMIT" \
    && cargo build --release --locked --bins

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    at-spi2-core ca-certificates dbus dbus-x11 git gir1.2-gtk-3.0 gir1.2-atspi-2.0 \
    libglib2.0-bin locales procps python3 python3-gi python3-requests \
    python3-pexpect python3-pyte x11-utils xvfb epiphany-browser \
    && locale-gen C.UTF-8 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash gui2tui

COPY --from=builder /src/target/release/gui2tui /usr/local/bin/gui2tui
COPY --from=builder /src/target/release/gui2tui-inspect /usr/local/libexec/gui2tui/gui2tui-inspect
COPY --from=builder /src/target/release/gui2tui-local /usr/local/libexec/gui2tui/gui2tui-local
COPY --from=builder /src/scripts/headless-session /usr/local/libexec/gui2tui/headless-session
COPY docker/entrypoint.sh /usr/local/bin/jev-anything-entrypoint
COPY docker/atspi_probe.py /opt/jev-anything/atspi_probe.py
COPY docker/fixture.py /opt/jev-anything/fixture.py
COPY docker/capture.py /opt/jev-anything/capture.py
COPY docker/terminal_probe.py /opt/jev-anything/terminal_probe.py
COPY docker/browser_fixture.py /opt/jev-anything/browser_fixture.py
COPY scripts/live_docker_test.py /opt/jev-anything/live_docker_test.py
COPY src /opt/jev-anything/src
COPY tests /opt/jev-anything/tests
COPY web /opt/jev-anything/web
ENV PYTHONPATH=/opt/jev-anything/src

RUN chmod +x /usr/local/bin/jev-anything-entrypoint /usr/local/libexec/gui2tui/headless-session \
    && chown -R gui2tui:gui2tui /opt/jev-anything

USER gui2tui
WORKDIR /opt/jev-anything
ENTRYPOINT ["/usr/local/bin/jev-anything-entrypoint"]
CMD ["python3", "-m", "jev_anything.live_server"]
