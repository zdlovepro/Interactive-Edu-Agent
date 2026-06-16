package com.interactive.edu.vo.user;

public record UserSessionView(
        String token,
        UserProfileView user
) {
}
