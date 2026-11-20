package com.stocks.contract.manualbot.dto;

import java.time.Instant;

/**
 * {@code GET /account/strategy}: the caller's own trading strategy as its owner saved it on the bot's page
 * ({@code ""} and nulls when none was saved: the claude-trader then uses the one in its agents.toml).
 */
public record BotStrategyDto(String strategy, Instant updatedAt, String updatedBy) {}
