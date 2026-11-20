package com.stocks.contract.manualbot.dto;

import java.time.Instant;

/** {@code GET /runner/bots}: one of the runner's owner's active bots with a strategy saved on its page. */
public record RunnerBotDto(String handle, String displayName, String strategy, Instant strategyUpdatedAt) {}
