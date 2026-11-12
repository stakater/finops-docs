# syntax=docker/dockerfile:1
FROM nginxinc/nginx-unprivileged:1.31-alpine
WORKDIR /usr/share/nginx/html/

# copy the entire application
COPY --from=content --chown=1001:root . .

COPY default.conf /etc/nginx/conf.d/

# set non-root user
USER 1001

LABEL name="FinOps Operator Documentation" \
      maintainer="Stakater <hello@stakater.com>" \
      vendor="Stakater" \
      release="1" \
      summary="Documentation for FinOps Operator"

EXPOSE 8080:8080/tcp

CMD ["nginx", "-g", "daemon off;"]