package com.interactive.edu.repository;

import com.interactive.edu.entity.SysUser;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface SysUserRepository extends JpaRepository<SysUser, String> {

    Optional<SysUser> findByUsernameIgnoreCase(String username);
}
