package com.interactive.edu.service.task;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interactive.edu.model.task.TaskStatePayload;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class TaskStateStore {

    private static final Duration DEFAULT_TTL = Duration.ofDays(2);

    private final ObjectMapper objectMapper;
    private final ObjectProvider<StringRedisTemplate> stringRedisTemplateProvider;
    private final Map<String, TaskStatePayload> localFallbackStore = new ConcurrentHashMap<>();

    public void save(String key, TaskStatePayload payload) {
        save(key, payload, DEFAULT_TTL);
    }

    public void save(String key, TaskStatePayload payload, Duration ttl) {
        if (!StringUtils.hasText(key) || payload == null) {
            return;
        }
        StringRedisTemplate redisTemplate = stringRedisTemplateProvider.getIfAvailable();
        if (redisTemplate != null) {
            try {
                redisTemplate.opsForValue().set(key, objectMapper.writeValueAsString(payload), ttl);
                return;
            } catch (Exception ex) {
                log.warn("Failed to write task state to Redis. key={}, reason={}", key, ex.getMessage());
            }
        }
        localFallbackStore.put(key, payload);
    }

    public Optional<TaskStatePayload> get(String key) {
        if (!StringUtils.hasText(key)) {
            return Optional.empty();
        }
        StringRedisTemplate redisTemplate = stringRedisTemplateProvider.getIfAvailable();
        if (redisTemplate != null) {
            try {
                String raw = redisTemplate.opsForValue().get(key);
                if (StringUtils.hasText(raw)) {
                    return Optional.of(objectMapper.readValue(raw, TaskStatePayload.class));
                }
            } catch (JsonProcessingException ex) {
                log.warn("Failed to parse task state JSON. key={}, reason={}", key, ex.getMessage());
            } catch (Exception ex) {
                log.warn("Failed to read task state from Redis. key={}, reason={}", key, ex.getMessage());
            }
        }
        return Optional.ofNullable(localFallbackStore.get(key));
    }

    public void delete(String key) {
        if (!StringUtils.hasText(key)) {
            return;
        }
        StringRedisTemplate redisTemplate = stringRedisTemplateProvider.getIfAvailable();
        if (redisTemplate != null) {
            try {
                redisTemplate.delete(key);
            } catch (Exception ex) {
                log.warn("Failed to delete task state from Redis. key={}, reason={}", key, ex.getMessage());
            }
        }
        localFallbackStore.remove(key);
    }
}
