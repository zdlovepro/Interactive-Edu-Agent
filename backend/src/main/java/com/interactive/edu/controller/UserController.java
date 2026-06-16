package com.interactive.edu.controller;

import com.interactive.edu.dto.BaseResponse;
import com.interactive.edu.service.user.AuthService;
import com.interactive.edu.vo.user.UserProfileView;
import com.interactive.edu.vo.user.UserSessionView;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/user")
@RequiredArgsConstructor
@Validated
public class UserController {

    private final AuthService authService;

    @PostMapping("/login")
    public BaseResponse<UserSessionView> login(@Valid @RequestBody LoginRequest request) {
        return BaseResponse.ok(authService.login(request.username(), request.password()));
    }

    @PostMapping("/register")
    public BaseResponse<UserSessionView> register(@Valid @RequestBody RegisterRequest request) {
        return BaseResponse.ok(authService.register(
                request.username(),
                request.password(),
                request.realName(),
                request.role()
        ));
    }

    @PostMapping("/logout")
    public BaseResponse<Void> logout(
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        authService.logout(authorizationHeader);
        return BaseResponse.ok(null);
    }

    @GetMapping("/profile")
    public BaseResponse<UserProfileView> profile(
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        return BaseResponse.ok(authService.getProfile(authorizationHeader));
    }

    public record LoginRequest(
            @NotBlank(message = "username must not be blank") String username,
            @NotBlank(message = "password must not be blank") String password
    ) {
    }

    public record RegisterRequest(
            @NotBlank(message = "username must not be blank") String username,
            @NotBlank(message = "password must not be blank") String password,
            @NotBlank(message = "realName must not be blank") String realName,
            @NotBlank(message = "role must not be blank") String role
    ) {
    }
}
