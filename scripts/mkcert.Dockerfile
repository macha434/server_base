FROM alpine:3

# mkcertの公式Linuxバイナリはglibc前提のため、alpine(musl)ではlibc6-compatが必要。
RUN apk add --no-cache wget libc6-compat \
    && wget -O /usr/local/bin/mkcert \
        https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64 \
    && chmod +x /usr/local/bin/mkcert

ENTRYPOINT ["mkcert"]
