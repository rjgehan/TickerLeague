package com.stocks.manualbot.web;

import com.stocks.contract.manualbot.dto.BotStrategyDto;
import com.stocks.contract.security.CurrentPlayer;
import com.stocks.manualbot.ManualBotService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * A bot's trading strategy as its owner saved it on the bot's page ({@code PUT /me/bots/{handle}/manual}). Under
 * {@code /api/v1/account/**}, so account:read; the claude-trader reads it with the bot's own key before every check-in.
 */
@RestController
@RequestMapping("/api/v1/account")
@Tag(name = "account", description = "The caller's account")
public class BotStrategyController {

  private final ManualBotService manual;

  public BotStrategyController(ManualBotService manual) {
    this.manual = manual;
  }

  @GetMapping("/strategy")
  @Operation(summary = "My trading strategy", description = "The strategy the caller's owner saved for it on the "
      + "bot's page (at most 4000 characters). \"\" when none was saved: the claude-trader then follows the one in "
      + "its agents.toml.")
  public BotStrategyDto getStrategy() {
    return manual.ownStrategy(CurrentPlayer.require());
  }
}
