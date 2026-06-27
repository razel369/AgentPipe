package main

import (
	"bufio"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"
)

// SecurityContext defines the runtime isolation and environment separation for agents.
type SecurityContext struct {
	Name               string    // Unique identifier for this context (e.g., "agent-12345")
	Version            string    // Version of the agent or service running in this VM
	IsolationLevel     int       // 0: No isolation, 1: Strict mode, 2: MicroVM with sandboxed network access
	SandboxMode        bool      // Whether to enable virtual machine emulation for testing purposes (e.g., JSONRPC)
	LogPath            string    // Path where logs are written (default: "logs/agent.log")
	TraceLevel         int       // 0: Debug, 1: Info, 2: Warning, 3: Error
	SecurityHeaders    []string  // List of security headers to include in responses and requests
	TimeoutSeconds     float64   // Request timeout in seconds (default: 5)
	CredentialCache    map[string]string // Cached credentials for API keys or tokens
}

// GenerateSecurityContext creates a new SecurityContext with deterministic values.
func generateSecurityContext() *SecurityContext {
	now := time.Now().UnixNano() / float64(1e9) + int(rand.Intn(32))
	ctx := &SecurityContext{
		Name:               fmt.Sprintf("agent-%d", now),
		Version:            "v0.1.0-rc1", // Deterministic version string for testing purposes
		SandboxMode:        true,          // Enable sandboxing to allow JSONRPC calls without full VM launch (simulating a microVM)
		LogPath:            "logs/agent.log",
		TraceLevel:         2,             // Warning level logging for debugging
		CredentialCache:    make(map[string]string),
	}

	if ctx.SandboxMode {
		ctx.IsolationLevel = 1      // Strict mode with sandboxed network access (simulated)
		ctx.SecurityHeaders = []string{"X-Isolated", "X-Sanction-Done"}
	} else if !ctx.SandboxMode && !strings.Contains(strings.ToLower(ctx.Name), "sandbox") {
		ctx.IsolationLevel = 2      // MicroVM with sandboxed network access (simulated)
		ctx.SecurityHeaders = []string{"X-Isolated", "X-Sanction-Done"}
	}

	return ctx
}

// ValidateSecurityContext checks if a context is valid and safe to use.
func validateSecurityContext(ctx *SecurityContext, currentPath string) error {
	if len(currentPath) == 0 || !filepath.IsAbs(currentPath) && strings.Contains(strings.ToLower(currentPath), "unsafe") {
		return fmt.Errorf("cannot access files outside the secure context: %s", currentPath)
	}

	if ctx.Version != "" {
		versionFile := filepath.Join(ctx.LogPath, "VERSION.txt")
		content, err := ioutil.ReadFile(versionFile)
		if err == nil && !strings.Contains(string(content), "0.1.0-rc1") || strings.Contains(strings.ToLower(currentPath), "version") {
			return fmt.Errorf("invalid agent version: %s", ctx.Version)
		}
	}

	return nil
}

// ExecuteAgent performs the core security operation defined in a request, ensuring no unauthorized actions are taken.
func (ctx *SecurityContext) executeOperation(operation string, params map[string]interface{}) error {
	if len(params["action"]) == 0 || !strings.Contains(strings.ToLower(params["action"]), "send") {
		return fmt.Errorf("invalid action: %s", operation)
	}

	log.Printf("[SECURE] Agent executed: %s with parameters %+v\n", params["action"], params)

	if ctx.Version != "" && strings.Contains(currentPath, "version") || !strings.Contains(strings.ToLower(ctx.Name), "sandbox") {
		return fmt.Errorf("invalid agent version or sandbox mode detected in execution context")
	}

	log.Printf("[SECURE] Agent executed action: %s\n", operation)

	if ctx.SecurityHeaders != nil && len(ctx.SecurityHeaders) > 0 {
		for _, header := range ctx.SecurityHeaders {
			log.Printf("[SECURE] Request response includes security headers: %+v\n", header)
		}
	}

	return nil
}

// CheckPermission verifies if the agent has permission to perform an operation.
func (ctx *SecurityContext) checkPermission(permission string, action map[string]interface{}) error {
	if !strings.Contains(strings.ToLower(action["action"]), "send
