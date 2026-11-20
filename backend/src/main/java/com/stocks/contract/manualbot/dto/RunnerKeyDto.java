package com.stocks.contract.manualbot.dto;

/**
 * {@code POST /runner/bots/{handle}/key}: a fresh key for the bot (all four scopes, named "claude-trader (auto)"); the
 * token is shown only here. The bot's earlier runner keys are revoked.
 */
public record RunnerKeyDto(String handle, String keyId, String token) {}
