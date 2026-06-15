FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /workspace/backend
COPY backend/pom.xml ./pom.xml
COPY backend/maven-settings.xml /root/.m2/settings.xml
RUN --mount=type=cache,target=/root/.m2/repository \
    set -eux; \
    for attempt in 1 2 3; do \
        mvn -s /root/.m2/settings.xml \
            -B \
            -DskipTests \
            -Dmaven.wagon.http.retryHandler.count=5 \
            -Dmaven.wagon.http.retryHandler.requestSentEnabled=true \
            -Dmaven.wagon.httpconnectionManager.ttlSeconds=120 \
            dependency:go-offline && break; \
        if [ "$attempt" -eq 3 ]; then \
            exit 1; \
        fi; \
        sleep $((attempt * 5)); \
    done
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.m2/repository \
    set -eux; \
    for attempt in 1 2 3; do \
        mvn -s /root/.m2/settings.xml \
            -B \
            -Dmaven.test.skip=true \
            -Dmaven.wagon.http.retryHandler.count=5 \
            -Dmaven.wagon.http.retryHandler.requestSentEnabled=true \
            -Dmaven.wagon.httpconnectionManager.ttlSeconds=120 \
            package && break; \
        if [ "$attempt" -eq 3 ]; then \
            exit 1; \
        fi; \
        sleep $((attempt * 5)); \
    done

FROM eclipse-temurin:17-jre-jammy

RUN set -eux; \
    sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' \
        -e 's|https://archive.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' \
        -e 's|http://security.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' \
        -e 's|https://security.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' \
        /etc/apt/sources.list \
        /etc/apt/sources.list.d/*.list \
        /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /workspace/backend/target/*.jar /app/app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
