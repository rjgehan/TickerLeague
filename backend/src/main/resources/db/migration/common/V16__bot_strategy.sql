-- =====================================================================================================================
-- V16: a bot's trading strategy, kept in the app so its owner (or the admin) can change it from the bot's page. The
-- claude-trader reads it with the bot's own key before every check-in (GET /account/strategy); when there is none it
-- falls back to the strategy in its agents.toml. Separate from manual_bot.instructions, which feed the copy-and-paste
-- prompts. Portable H2 2.4 + PostgreSQL 18 (§8 portability rules); com.stocks.manualbot is the only writer.
-- =====================================================================================================================

CREATE TABLE bot_strategy (
  player_id   BIGINT        PRIMARY KEY REFERENCES player(id),    -- the AI bot
  strategy    VARCHAR(4000) NOT NULL,                             -- at most 4000 characters ('' = use agents.toml)
  updated_by  BIGINT        NOT NULL REFERENCES player(id),       -- the human who saved it
  updated_at  TIMESTAMP WITH TIME ZONE NOT NULL
);
