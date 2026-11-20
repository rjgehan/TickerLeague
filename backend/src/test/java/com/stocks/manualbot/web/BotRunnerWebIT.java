package com.stocks.manualbot.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

import com.stocks.config.StocksProperties;
import com.stocks.testkit.Fixtures;
import com.stocks.testkit.WebSession;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MvcResult;

/**
 * The claude-trader's runner key: the owner issues it on a browser (recent password check); with it the trader lists
 * the owner's bots that have a strategy saved and gets a key for each, and can do nothing else.
 */
class BotRunnerWebIT extends ManualBotsTestBase {

  @Autowired StocksProperties properties;

  @Test
  void theOwnerIssuesARunnerKeyThatFindsTheirBotsAndGetsTheirKeys() throws Exception {
    Fixtures.PlayerRef idle = fx.ai("ri" + next(), owner);              // no strategy saved: not listed
    as(ownerP, put(console(bot) + "/manual").contentType(MediaType.APPLICATION_JSON)
        .content("{\"strategy\": \"Hold QQQ above its 200-day.\"}"));

    WebSession s = WebSession.login(mvc, owner.handle(), Fixtures.PASSWORD);
    MvcResult issued = s.perform(post("/api/v1/me/bots/runner-key"));
    assertThat(issued.getResponse().getStatus()).as(WebSession.contentOf(issued)).isEqualTo(201);
    String runner = json(issued.getResponse(), "$.token");
    List<String> scopes = json(issued.getResponse(), "$.key.scopes");
    assertThat(scopes).containsExactly("bots:run");

    MockHttpServletResponse bots = bearer(get("/api/v1/runner/bots"), runner);
    assertThat(bots.getStatus()).as(bots.getContentAsString()).isEqualTo(200);
    List<String> handles = json(bots, "$[*].handle");
    assertThat(handles).containsExactly(bot.handle()).doesNotContain(idle.handle());
    assertThat((String) json(bots, "$[0].strategy")).isEqualTo("Hold QQQ above its 200-day.");

    MockHttpServletResponse key = bearer(post("/api/v1/runner/bots/" + bot.handle() + "/key"), runner);
    assertThat(key.getStatus()).as(key.getContentAsString()).isEqualTo(201);
    String botKey = json(key, "$.token");
    MockHttpServletResponse strategy = bearer(get("/api/v1/account/strategy"), botKey);
    assertThat((String) json(strategy, "$.strategy")).isEqualTo("Hold QQQ above its 200-day.");

    String second = json(bearer(post("/api/v1/runner/bots/" + bot.handle() + "/key"), runner), "$.token");
    assertThat(bearer(get("/api/v1/account/strategy"), botKey).getStatus()).as("the old key ends").isEqualTo(401);
    assertThat(bearer(get("/api/v1/account/strategy"), second).getStatus()).isEqualTo(200);

    // the runner key does nothing else, and only for the owner's bots with a strategy
    assertThat(bearer(post("/api/v1/runner/bots/" + idle.handle() + "/key"), runner).getStatus()).isEqualTo(403);
    Fixtures.PlayerRef theirs = fx.ai("rt" + next(), stranger);
    assertThat(bearer(post("/api/v1/runner/bots/" + theirs.handle() + "/key"), runner).getStatus()).isEqualTo(404);
    assertThat(bearer(get("/api/v1/account"), runner).getStatus()).isEqualTo(403);
    assertThat(bearer(get("/api/v1/runner/bots"), second).getStatus()).as("a bot key is no runner").isEqualTo(403);

    // a new runner key replaces the old one
    String next = json(s.perform(post("/api/v1/me/bots/runner-key")).getResponse(), "$.token");
    assertThat(bearer(get("/api/v1/runner/bots"), runner).getStatus()).isEqualTo(401);
    assertThat(bearer(get("/api/v1/runner/bots"), next).getStatus()).isEqualTo(200);
  }

  @Test
  void onlyABotOwnerOnABrowserGetsARunnerKey() throws Exception {
    WebSession s = WebSession.login(mvc, stranger.handle(), Fixtures.PASSWORD);
    MvcResult none = s.perform(post("/api/v1/me/bots/runner-key"));
    assertThat(none.getResponse().getStatus()).isEqualTo(403);
    String key = fx.apiKey(owner, properties.security().apiKeyPepper());
    assertThat(bearer(post("/api/v1/me/bots/runner-key"), key).getStatus()).isEqualTo(403);
  }

  private MockHttpServletResponse bearer(org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder r,
                                         String token) throws Exception {
    return mvc.perform(r.header("Authorization", "Bearer " + token)).andReturn().getResponse();
  }
}
