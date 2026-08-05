# Jenkins LTS + Docker CLI (host docker.sock is mounted at runtime)
FROM jenkins/jenkins:lts

USER root

# Docker CLI only — engine comes from /var/run/docker.sock on the host
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
      | tar -xz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker \
    && groupadd -f docker \
    && usermod -aG docker jenkins \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER jenkins
