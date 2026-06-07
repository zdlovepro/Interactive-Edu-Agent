package com.interactive.edu.config;

import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

@Configuration
@ConditionalOnClass(name = "jakarta.persistence.Entity")
@Profile({"full", "prod"})
@EnableJpaAuditing
public class JpaAuditConfig {
}
