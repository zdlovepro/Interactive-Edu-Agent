package com.interactive.edu.service.user;

import com.interactive.edu.entity.SysUser;
import com.interactive.edu.exception.BusinessException;
import com.interactive.edu.exception.ErrorCode;
import com.interactive.edu.repository.SysUserRepository;
import com.interactive.edu.vo.user.UserProfileView;
import com.interactive.edu.vo.user.UserSessionView;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private static final String TEACHER_USERNAME = "teacher";
    private static final String STUDENT_USERNAME = "student";
    private static final String TEACHER_PASSWORD = "teacher123";
    private static final String STUDENT_PASSWORD = "student123";
    private static final String PASSWORD_PREFIX = "sha256$";

    private final ObjectProvider<SysUserRepository> sysUserRepositoryProvider;

    private final ConcurrentMap<String, LocalUserState> localUsersById = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, String> localUserIdsByUsername = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, AuthenticatedUser> tokenStore = new ConcurrentHashMap<>();

    @PostConstruct
    void seedDefaultUsers() {
        if (isPersistentMode()) {
            ensurePersistentUser("user_teacher_demo", TEACHER_USERNAME, "Demo Teacher", "TEACHER", TEACHER_PASSWORD);
            ensurePersistentUser("user_student_demo", STUDENT_USERNAME, "Demo Student", "STUDENT", STUDENT_PASSWORD);
            return;
        }

        putLocalUser(new LocalUserState(
                "user_teacher_demo",
                TEACHER_USERNAME,
                "Demo Teacher",
                "TEACHER",
                encodePassword(TEACHER_PASSWORD)
        ));
        putLocalUser(new LocalUserState(
                "user_student_demo",
                STUDENT_USERNAME,
                "Demo Student",
                "STUDENT",
                encodePassword(STUDENT_PASSWORD)
        ));
    }

    public UserSessionView login(String username, String password) {
        String normalizedUsername = normalizeUsername(username);
        String normalizedPassword = normalizePassword(password);
        AuthenticatedUser user = authenticate(normalizedUsername, normalizedPassword);
        return createSession(user);
    }

    public UserSessionView register(String username, String password, String realName, String role) {
        String normalizedUsername = normalizeUsername(username);
        String normalizedPassword = normalizePassword(password);
        String normalizedRealName = normalizeRealName(realName, normalizedUsername);
        String normalizedRole = normalizeRegisterRole(role);

        if (isPersistentMode()) {
            if (sysUserRepository().findByUsernameIgnoreCase(normalizedUsername).isPresent()) {
                throw new BusinessException(ErrorCode.STATE_CONFLICT, "Username already exists");
            }

            SysUser user = new SysUser();
            user.setId("user_" + UUID.randomUUID().toString().replace("-", ""));
            user.setUsername(normalizedUsername);
            user.setRealName(normalizedRealName);
            user.setRole(normalizedRole);
            user.setPassword(encodePassword(normalizedPassword));
            user.setCreateTime(LocalDateTime.now());
            user.setUpdateTime(LocalDateTime.now());
            SysUser savedUser = sysUserRepository().save(user);
            log.info("User registered. userId={}, username={}, role={}", savedUser.getId(), savedUser.getUsername(), savedUser.getRole());
            return createSession(toAuthenticatedUser(savedUser));
        }

        String normalizedLookupKey = normalizedUsername.toLowerCase(Locale.ROOT);
        if (localUserIdsByUsername.containsKey(normalizedLookupKey)) {
            throw new BusinessException(ErrorCode.STATE_CONFLICT, "Username already exists");
        }

        LocalUserState user = new LocalUserState(
                "user_" + UUID.randomUUID().toString().replace("-", ""),
                normalizedUsername,
                normalizedRealName,
                normalizedRole,
                encodePassword(normalizedPassword)
        );
        putLocalUser(user);
        log.info("User registered in local mode. userId={}, username={}, role={}", user.id(), user.username(), user.role());
        return createSession(user.toAuthenticatedUser());
    }

    private UserSessionView createSession(AuthenticatedUser user) {
        String token = "iea_" + UUID.randomUUID().toString().replace("-", "");
        tokenStore.put(token, user);
        log.info("User logged in. userId={}, username={}, role={}", user.id(), user.username(), user.role());
        return new UserSessionView(token, toProfileView(user));
    }

    public void logout(String authorizationHeader) {
        String token = extractToken(authorizationHeader);
        if (!StringUtils.hasText(token)) {
            return;
        }
        tokenStore.remove(token.trim());
    }

    public UserProfileView getProfile(String authorizationHeader) {
        return toProfileView(requireUser(authorizationHeader));
    }

    public AuthenticatedUser requireUser(String authorizationHeader) {
        String token = extractToken(authorizationHeader);
        if (!StringUtils.hasText(token)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Please log in first");
        }
        return requireUserByToken(token);
    }

    public AuthenticatedUser requireUserByToken(String rawToken) {
        String token = rawToken == null ? "" : rawToken.trim();
        if (!StringUtils.hasText(token)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Please log in first");
        }

        AuthenticatedUser cached = tokenStore.get(token);
        if (cached == null) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Your login session has expired. Please sign in again");
        }
        return cached;
    }

    public AuthenticatedUser findUserById(String userId) {
        if (!StringUtils.hasText(userId)) {
            throw new BusinessException(ErrorCode.NOT_FOUND, "User not found");
        }

        if (isPersistentMode()) {
            SysUser user = sysUserRepository().findById(userId.trim())
                    .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND, "User not found"));
            return toAuthenticatedUser(user);
        }

        LocalUserState user = localUsersById.get(userId.trim());
        if (user == null) {
            throw new BusinessException(ErrorCode.NOT_FOUND, "User not found");
        }
        return user.toAuthenticatedUser();
    }

    public boolean isTeacherUser(String userId) {
        try {
            return "TEACHER".equalsIgnoreCase(findUserById(userId).role());
        } catch (BusinessException ex) {
            return false;
        }
    }

    public String extractToken(String authorizationHeader) {
        if (!StringUtils.hasText(authorizationHeader)) {
            return null;
        }

        String trimmed = authorizationHeader.trim();
        if (trimmed.regionMatches(true, 0, "Bearer ", 0, 7)) {
            return trimmed.substring(7).trim();
        }
        return trimmed;
    }

    private AuthenticatedUser authenticate(String username, String password) {
        if (isPersistentMode()) {
            SysUser user = sysUserRepository().findByUsernameIgnoreCase(username)
                    .orElseThrow(() -> new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid username or password"));
            verifyPassword(password, user.getPassword());
            return toAuthenticatedUser(user);
        }

        String userId = localUserIdsByUsername.get(username.toLowerCase(Locale.ROOT));
        if (!StringUtils.hasText(userId)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid username or password");
        }
        LocalUserState user = localUsersById.get(userId);
        if (user == null) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid username or password");
        }
        verifyPassword(password, user.passwordHash());
        return user.toAuthenticatedUser();
    }

    private void ensurePersistentUser(String id, String username, String realName, String role, String password) {
        if (sysUserRepository().findByUsernameIgnoreCase(username).isPresent()) {
            return;
        }

        SysUser user = new SysUser();
        user.setId(id);
        user.setUsername(username);
        user.setRealName(realName);
        user.setRole(role);
        user.setPassword(encodePassword(password));
        user.setCreateTime(LocalDateTime.now());
        user.setUpdateTime(LocalDateTime.now());
        sysUserRepository().save(user);
        log.info("Seeded demo user. username={}, role={}", username, role);
    }

    private void putLocalUser(LocalUserState user) {
        localUsersById.put(user.id(), user);
        localUserIdsByUsername.put(user.username().toLowerCase(Locale.ROOT), user.id());
    }

    private UserProfileView toProfileView(AuthenticatedUser user) {
        return new UserProfileView(user.id(), user.username(), user.realName(), user.role());
    }

    private AuthenticatedUser toAuthenticatedUser(SysUser user) {
        return new AuthenticatedUser(
                user.getId(),
                user.getUsername(),
                StringUtils.hasText(user.getRealName()) ? user.getRealName().trim() : user.getUsername(),
                defaultRole(user.getRole())
        );
    }

    private String normalizeUsername(String username) {
        if (!StringUtils.hasText(username)) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "Username must not be blank");
        }
        return username.trim();
    }

    private String normalizePassword(String password) {
        if (!StringUtils.hasText(password)) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "Password must not be blank");
        }
        if (password.length() < 6) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "Password must be at least 6 characters");
        }
        return password;
    }

    private String normalizeRealName(String realName, String fallbackUsername) {
        String normalized = normalizeOptionalValue(realName);
        if (!StringUtils.hasText(normalized)) {
            return fallbackUsername;
        }
        if (normalized.length() > 64) {
            throw new BusinessException(ErrorCode.PARAM_ERROR, "Real name must be at most 64 characters");
        }
        return normalized;
    }

    private String normalizeRegisterRole(String role) {
        String normalized = StringUtils.hasText(role) ? role.trim().toUpperCase(Locale.ROOT) : "STUDENT";
        return switch (normalized) {
            case "TEACHER", "STUDENT" -> normalized;
            default -> throw new BusinessException(ErrorCode.PARAM_ERROR, "Role must be TEACHER or STUDENT");
        };
    }

    private void verifyPassword(String rawPassword, String storedPassword) {
        if (!encodePassword(rawPassword).equals(storedPassword)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "Invalid username or password");
        }
    }

    private String encodePassword(String rawPassword) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] encoded = digest.digest(rawPassword.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(PASSWORD_PREFIX);
            for (byte current : encoded) {
                builder.append(Character.forDigit((current >> 4) & 0xF, 16));
                builder.append(Character.forDigit(current & 0xF, 16));
            }
            return builder.toString();
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to encode password", ex);
        }
    }

    private String defaultRole(String role) {
        String normalized = StringUtils.hasText(role) ? role.trim().toUpperCase(Locale.ROOT) : "STUDENT";
        return switch (normalized) {
            case "TEACHER", "ADMIN" -> normalized;
            default -> "STUDENT";
        };
    }

    private String normalizeOptionalValue(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }

    private boolean isPersistentMode() {
        return sysUserRepositoryProvider.getIfAvailable() != null;
    }

    private SysUserRepository sysUserRepository() {
        SysUserRepository repository = sysUserRepositoryProvider.getIfAvailable();
        if (repository == null) {
            throw new IllegalStateException("SysUserRepository is unavailable in the current profile");
        }
        return repository;
    }

    public record AuthenticatedUser(
            String id,
            String username,
            String realName,
            String role
    ) {
        public boolean isTeacher() {
            return "TEACHER".equalsIgnoreCase(role) || "ADMIN".equalsIgnoreCase(role);
        }

        public boolean isStudent() {
            return "STUDENT".equalsIgnoreCase(role);
        }
    }

    private record LocalUserState(
            String id,
            String username,
            String realName,
            String role,
            String passwordHash
    ) {
        private AuthenticatedUser toAuthenticatedUser() {
            return new AuthenticatedUser(id, username, realName, role);
        }
    }
}
