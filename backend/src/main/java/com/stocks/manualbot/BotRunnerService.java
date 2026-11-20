package com.stocks.manualbot;

import com.stocks.audit.AuditCategory;
import com.stocks.audit.AuditEntry;
import com.stocks.audit.AuditOutcome;
import com.stocks.audit.AuditService;
import com.stocks.common.domain.AuthMethod;
import com.stocks.common.domain.PlayerKind;
import com.stocks.common.domain.PlayerStatus;
import com.stocks.common.error.ApiException;
import com.stocks.common.error.ErrorCode;
import com.stocks.common.web.Text;
import com.stocks.contract.identity.dto.ApiKeyCreatedDto;
import com.stocks.contract.manualbot.dto.RunnerBotDto;
import com.stocks.contract.manualbot.dto.RunnerKeyDto;
import com.stocks.contract.security.PlayerPrincipal;
import com.stocks.contract.security.RequestMeta;
import com.stocks.contract.security.Scopes;
import com.stocks.identity.ApiKeyService;
import com.stocks.identity.PlayerRecord;
import com.stocks.identity.PlayerService;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Service;

/**
 * The claude-trader's runner key ({@link Scopes#BOTS_RUN}): its owner issues it once on the Admin -> Bots page; with
 * it the trader lists the owner's bots that have a strategy saved on their page and gets a key for each, so a new bot
 * starts trading without anyone copying keys to the server. The runner key itself can do nothing else.
 */
@Service
public class BotRunnerService {

  /** The runner key's name; issuing a new one revokes the old ones. */
  public static final String RUNNER_KEY_NAME = "claude-trader runner";
  /** A bot key minted for the runner; minting a new one revokes the old ones. */
  public static final String BOT_KEY_NAME = "claude-trader (auto)";

  private final ManualBotRepository repo;
  private final PlayerService players;
  private final ApiKeyService apiKeys;
  private final AuditService audit;

  public BotRunnerService(ManualBotRepository repo, PlayerService players, ApiKeyService apiKeys,
                          AuditService audit) {
    this.repo = repo;
    this.players = players;
    this.apiKeys = apiKeys;
    this.audit = audit;
  }

  /** {@code POST /me/bots/runner-key}: a person on a browser who owns at least one bot; the old runner keys end. */
  public ApiKeyCreatedDto issueRunnerKey(PlayerPrincipal human, RequestMeta meta) {
    if (human == null || human.authMethod() != AuthMethod.SESSION || human.kind() != PlayerKind.HUMAN) {
      throw ApiException.of(ErrorCode.FORBIDDEN, "The runner key needs a person signed in on a browser.");
    }
    if (repo.botsOwnedBy(human.playerId()).isEmpty()) {
      throw ApiException.of(ErrorCode.FORBIDDEN, "You own no bots, so there is nothing for a runner to run.");
    }
    for (String old : repo.liveKeyIdsNamed(human.playerId(), RUNNER_KEY_NAME)) {
      apiKeys.revoke(old, human.playerId(), human.playerId());
    }
    ApiKeyService.IssuedKey key = apiKeys.issue(human.playerId(), RUNNER_KEY_NAME, Set.of(Scopes.BOTS_RUN), null,
        human.playerId());
    audit.record(AuditEntry.of(AuditCategory.KEY, "KEY_ISSUE", AuditOutcome.OK).withActor(human).withMeta(meta)
        .withTarget("api_key", key.keyId()).withDetail("player", human.handle())
        .withDetail("scopes", List.of(Scopes.BOTS_RUN)).withDetail("personal", true));
    return apiKeys.created(key);
  }

  /** {@code GET /runner/bots}: the caller's active bots with a strategy saved on their page, by handle. */
  public List<RunnerBotDto> bots(PlayerPrincipal runner) {
    requireRunner(runner);
    List<RunnerBotDto> out = new ArrayList<>();
    for (long id : repo.botsOwnedBy(runner.playerId())) {
      PlayerRecord bot = players.byId(id).orElse(null);
      if (bot == null || bot.status() != PlayerStatus.ACTIVE) {
        continue;
      }
      repo.strategy(id).filter(r -> !r.instructions().isBlank()).ifPresent(r ->
          out.add(new RunnerBotDto(bot.handle(), bot.displayName(), r.instructions(), r.updatedAt())));
    }
    return out;
  }

  /** {@code POST /runner/bots/{handle}/key}: a new key (all four scopes) for one of those bots; its old ones end. */
  public RunnerKeyDto botKey(PlayerPrincipal runner, String handle, RequestMeta meta) {
    requireRunner(runner);
    PlayerRecord bot = players.byHandle(handle).orElse(null);
    boolean mine = bot != null && bot.kind() == PlayerKind.AI && bot.ownerPlayerId() != null
        && bot.ownerPlayerId() == runner.playerId();
    if (!mine) {
      throw ApiException.of(ErrorCode.PLAYER_NOT_FOUND, "You own no bot '" + Text.clip(String.valueOf(handle), 40)
          + "'.");
    }
    if (bot.status() != PlayerStatus.ACTIVE) {
      throw ApiException.of(ErrorCode.FORBIDDEN, "@" + bot.handle() + " is " + bot.status().name().toLowerCase()
          + ".");
    }
    if (repo.strategy(bot.id()).map(r -> r.instructions().isBlank()).orElse(true)) {
      throw ApiException.of(ErrorCode.FORBIDDEN, "@" + bot.handle() + " has no strategy saved on its page.");
    }
    for (String old : repo.liveKeyIdsNamed(bot.id(), BOT_KEY_NAME)) {
      apiKeys.revoke(old, bot.id(), runner.playerId());
    }
    ApiKeyService.IssuedKey key = apiKeys.issue(bot.id(), BOT_KEY_NAME, Scopes.ALL, null, runner.playerId());
    audit.record(AuditEntry.of(AuditCategory.KEY, "KEY_ISSUE", AuditOutcome.OK).withActor(runner).withMeta(meta)
        .withTarget("api_key", key.keyId()).withDetail("player", bot.handle()).withDetail("runner", true));
    return new RunnerKeyDto(bot.handle(), key.keyId(), key.token());
  }

  private static void requireRunner(PlayerPrincipal p) {
    if (p == null || p.authMethod() != AuthMethod.API_KEY || p.kind() != PlayerKind.HUMAN
        || !p.scopes().contains(Scopes.BOTS_RUN)) {
      throw ApiException.of(ErrorCode.FORBIDDEN, "Only a runner key (scope bots:run) can do this.");
    }
  }
}
