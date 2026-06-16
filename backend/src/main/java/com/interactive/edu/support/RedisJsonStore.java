package com.interactive.edu.support;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.time.Duration;

@Component
@RequiredArgsConstructor
@Slf4j
public class RedisJsonStore {

    private final ObjectProvider<StringRedisTemplate> redisTemplateProvider;

    public void put(String key, String value, Duration ttl) {
        if (!StringUtils.hasText(key) || value == null) {
            return;
        }
        StringRedisTemplate redisTemplate = redisTemplateProvider.getIfAvailable();
        if (redisTemplate == null) {
            return;
        }
        try {
            if (ttl == null || ttl.isZero() || ttl.isNegative()) {
                redisTemplate.opsForValue().set(key, value);
            } else {
                redisTemplate.opsForValue().set(key, value, ttl);
            }
        } catch (Exception ex) {
            log.warn("Failed to write JSON payload into Redis. key={}, reason={}", key, ex.getMessage());
        }
    }

    public String get(String key) {
        if (!StringUtils.hasText(key)) {
            return null;
        }
        StringRedisTemplate redisTemplate = redisTemplateProvider.getIfAvailable();
        if (redisTemplate == null) {
            return null;
        }
        try {
            return redisTemplate.opsForValue().get(key);
        } catch (Exception ex) {
            log.warn("Failed to read JSON payload from Redis. key={}, reason={}", key, ex.getMessage());
            return null;
        }
    }

    public void delete(String key) {
        if (!StringUtils.hasText(key)) {
            return;
        }
        StringRedisTemplate redisTemplate = redisTemplateProvider.getIfAvailable();
        if (redisTemplate == null) {
            return;
        }
        try {
            redisTemplate.delete(key);
        } catch (Exception ex) {
            log.warn("Failed to delete Redis key. key={}, reason={}", key, ex.getMessage());
        }
    }
}
