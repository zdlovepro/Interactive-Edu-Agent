package com.interactive.edu.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

@Configuration
@Profile("full")
@EnableJpaAuditing
public class FullJpaAuditingConfig {
}
