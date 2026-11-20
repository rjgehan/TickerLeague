package com.stocks.manualbot.web;

import com.stocks.contract.identity.dto.ApiKeyCreatedDto;
import com.stocks.contract.manualbot.dto.RunnerBotDto;
import com.stocks.contract.manualbot.dto.RunnerKeyDto;
import com.stocks.contract.security.CurrentPlayer;
import com.stocks.contract.security.PlayerPrincipal;
import com.stocks.manualbot.BotRunnerService;
import com.stocks.security.RecentAuth;
import com.stocks.security.RequestMetas;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * The claude-trader's runner key: issued by a bot owner on a browser ({@code /me/**}: session only, CSRF, recent
 * password check); used by the trader under {@code /runner/**} (scope bots:run, route rule in {@code SecurityConfig})
 * to find the owner's bots and get their keys.
 */
@RestController
@RequestMapping("/api/v1")
@Tag(name = "agents", description = "AI players: run reports and the public AI journal (Phase 2)")
public class BotRunnerController {

  private final BotRunnerService runner;

  public BotRunnerController(BotRunnerService runner) {
    this.runner = runner;
  }

  @PostMapping("/me/bots/runner-key")
  @ResponseStatus(HttpStatus.CREATED)
  @RecentAuth
  @Operation(summary = "Issue the claude-trader's runner key", description = "Session only, recent password check, "
      + "a person who owns at least one bot. The key has the single scope bots:run: it lists your bots that have a "
      + "strategy saved on their page and gets a key for each, and nothing else. Your earlier runner keys are "
      + "revoked. Put it in the trader's agents.toml as [runner] key. The token is shown once.")
  public ApiKeyCreatedDto issueRunnerKey(HttpServletRequest request) {
    PlayerPrincipal human = CurrentPlayer.require();
    return runner.issueRunnerKey(human, RequestMetas.of(request, human));
  }

  @GetMapping("/runner/bots")
  @Operation(summary = "The bots a runner key runs", description = "Runner key only (bots:run): the key owner's "
      + "active bots with a strategy saved on their page, by handle.")
  public List<RunnerBotDto> getRunnerBots() {
    return runner.bots(CurrentPlayer.require());
  }

  @PostMapping("/runner/bots/{handle}/key")
  @ResponseStatus(HttpStatus.CREATED)
  @Operation(summary = "A new key for one of the runner's bots", description = "Runner key only (bots:run). All four "
      + "scopes, named \"claude-trader (auto)\"; the bot's earlier runner-issued keys are revoked. The token is shown "
      + "once. Errors: PLAYER_NOT_FOUND (not your bot), FORBIDDEN (frozen, or no strategy saved).")
  public RunnerKeyDto issueRunnerBotKey(@PathVariable("handle") String handle, HttpServletRequest request) {
    PlayerPrincipal runnerKey = CurrentPlayer.require();
    return runner.botKey(runnerKey, handle, RequestMetas.of(request, runnerKey));
  }
}
