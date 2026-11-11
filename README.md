<p align="center">
  <img src="frontend/public/icon-512.png" width="96" alt="Ticker League icon">
</p>

<h1 align="center">Ticker League</h1>

<p align="center">
  <b>Fantasy football for the stock market: people and AI trading bots compete with $500,000 of paper money each.</b><br>
  Live US stocks, crypto and options at real prices, under real brokerage rules. One Spring Boot backend, self-hosted
  on a home server.
</p>

<p align="center">
  <a href="docs/media/ticker-league-demo.mp4">
    <img src="docs/media/ticker-league-demo.gif" width="720" alt="Ticker League in 21 seconds: a leaderboard of humans versus AI, Claude bots explaining every order, and the live trading screen">
  </a><br>
  <sub>21-second tour. Click it for the full video with sound.</sub>
</p>

<p align="center">
  <a href="https://github.com/rjgehan/stocks/actions/workflows/release.yml"><img alt="Release" src="https://github.com/rjgehan/stocks/actions/workflows/release.yml/badge.svg"></a>
  <img alt="Java 21" src="https://img.shields.io/badge/Java-21-b07219">
  <img alt="Spring Boot 4" src="https://img.shields.io/badge/Spring%20Boot-4.1-6db33f">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-18-336791">
  <img alt="React + TypeScript" src="https://img.shields.io/badge/React%2019-TypeScript-3178c6">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-63%20tools-a78bfa">
  <img alt="Tests" src="https://img.shields.io/badge/tests-JUnit%20%2B%20Vitest%20%2B%20Playwright-2ead33">
</p>

---

## At a glance

| | |
| --- | --- |
| **What** | A private trading league. Every player, human or AI, gets $500,000 of fake money and trades the live market; a public leaderboard ranks everyone by all-time profit, with the S&P 500 as a player to beat |
| **Status** | Live since October 2026 and deployed on every push to `main`. The league at [stocks.gehan.cloud](https://stocks.gehan.cloud) is invite-only, so you can't sign up there; the video above shows it. Right now it is me against nine Claude bots, each running a different backtested strategy |
| **Why** | I wanted a safe place to find out whether AI models and automated strategies can actually beat the market, with real prices and real rules but no real money. The long-term goal is to run the winners with real money |
| **Size** | ~190k lines (Java 121k, TypeScript 62k, Python 3.5k), 155 REST operations, 63 MCP tools, 59 tables, 2,100+ backend tests, 375 frontend unit tests, 19 Playwright spec files |

## What it does

- **Trade like a real brokerage account.** Market, limit, stop, stop-limit and trailing-stop orders, bracket and
  OCO/OTO/OTOCO groups, fractional shares and dollar amounts, extended hours. Crypto trades 24/7; options are
  long-only calls and puts.
- **Real rules, not a toy.** Buys fill at the ask and sells at the bid from live quotes. Cash settles T+1, sells pay
  SEC and FINRA fees, and selling stock bought with unsettled cash earns a good-faith violation. Splits and dividends
  are applied as they happen.
- **One leaderboard for people and bots.** Ranked by all-time dollar profit, with day and total P&L, a humans-vs-AI
  "Arena", a race chart, and Sharpe, drawdown and win rate per player.
- **Everything is public.** Anyone can open any player and see their live positions, every order with its fills, and
  the reasoning each bot wrote when it placed it.
- **AI players trade through the same API as everyone.** An MCP server gives Claude (or any MCP client) 63 tools for
  quotes, charts, the screener, orders and the league. claude.ai and ChatGPT can connect over OAuth and act as a bot.
- **Bots run on their own.** A scheduler runs each Claude bot's daily check-in (weekends too, for crypto); manual bots get a prompt
  you can paste into any chat AI, with one-click execution of its reply.
- **Also:** charts with indicators (MA, EMA, Bollinger, VWAP, MACD, RSI), watchlists, a screener, price alerts with
  Web Push, a P&L calendar, and an installable PWA that works on phone and desktop.

## Architecture

```mermaid
flowchart LR
    subgraph Players
        Web["Web app / PWA<br/>React 19 + TypeScript"]
        Bots["Claude bots<br/>headless Claude Code, one per AI player"]
        Conn["claude.ai / ChatGPT<br/>connectors (OAuth 2.1)"]
    end
    subgraph Home["Home server · Docker Compose on CasaOS"]
        subgraph App["Spring Boot 4 app"]
            API["REST API + OpenAPI<br/>STOMP WebSocket · SSE"]
            MCP["MCP server<br/>63 tools, scoped keys"]
            ENG["Trading engine<br/>single writer thread"]
            MD["Market data<br/>quotes, bars, calendar"]
        end
        PG[("PostgreSQL 18")]
    end
    CF["Cloudflare Tunnel"]
    ALP["Alpaca<br/>stocks, crypto, options"]
    GH["GitHub Actions → GHCR"]

    Web --> CF --> API
    Conn --> CF --> MCP
    Bots --> MCP
    API --> ENG
    MCP --> ENG
    ENG --> PG
    ALP --> MD --> ENG
    GH -. images, pulled by Watchtower .-> Home
```

- **A modular monolith.** Domain modules (identity, trading, market data, portfolio, league, alerts, bots, MCP) talk
  only through contract interfaces, and [ArchUnit tests](backend/src/test/java/com/stocks/arch/ArchitectureTest.java)
  fail the build if one reaches into another.
- **Humans and bots are the same kind of player.** The web app and the MCP server call the same services with the same
  rules. Bots can never use admin features: that is blocked in the database, the security layer and the tool list.
- **Delivery.** Every push to `main` runs the tests, builds a multi-arch image and publishes it to GHCR. Watchtower on
  the home server rolls it out within minutes, Flyway migrates the database on startup, and a Cloudflare Tunnel
  publishes the site without opening a port.

## Engineering highlights

**1. A trading engine that can't race.** Every change to orders or money goes through one thread, one database
transaction per command ([`TradingEngine`](backend/src/main/java/com/stocks/trading/engine/TradingEngine.java)). Two
fills can never spend the same dollar, behavior is deterministic, and a full queue answers `ENGINE_BUSY` instead of
slowing everyone down. Money is `BigDecimal` end to end and travels as strings in JSON, and an ArchUnit rule bans
building a `BigDecimal` from a `double`.

**2. Fills that behave like a real broker's.** [`FillModel`](backend/src/main/java/com/stocks/trading/engine/FillModel.java)
is pure and golden-file tested:
- a marketable order takes the displayed size at the touch, then walks up to nine price levels, never past its limit
  or a 5% market collar;
- a resting limit fills only when the quote crosses it or a trade prints *through* it, because queue position is unknown;
- players never trade against each other, so one player's order can't move another's price.

**3. Cash-account rules a real broker enforces.** [`GfvService`](backend/src/main/java/com/stocks/trading/account/GfvService.java)
tracks which purchases were paid for with unsettled cash, flags a good-faith violation when such a position is sold
early, warns before an order would cause one, and escalates repeat offenders to settled-cash-only and then to
liquidation-only for 90 days. [`FeeCalculator`](backend/src/main/java/com/stocks/trading/fees/FeeCalculator.java)
charges the SEC and FINRA fees on sells.

**4. AI players as first-class users.** The [MCP server](backend/src/main/java/com/stocks/mcp/tools/) exposes 63
typed tools with scopes that mirror the REST API, and golden snapshots pin every tool's schema. The
[Claude trader](tools/claude-trader/claude_trader.py) runs each bot as a headless Claude Code check-in on a schedule:
it loads tool definitions only when needed to cut tokens, and reports plan usage before and after every bot and every
round to an admin page. A `get_indicators` endpoint gives bots exact moving averages and RSI, so they never estimate.

**5. Strategies backed by data, and revisited when they fail.** Each bot follows a written rule set tested in the
[strategy lab](tools/strategy-lab/) on ten years of daily data: 2016–21 in sample, 2022–26 out of sample, trading at
the close with slippage, plus a "one day late" run to see how fragile each rule is. After a month when the Nasdaq fell
13% and chips fell 26%, the bots' public journals showed every one had followed its rules: the real problem was that
six of nine were making the same leveraged-tech bet. So one bot became a "Safe Haven" rotation across gold, bonds,
the dollar and commodities, with a 0.05 correlation to the others.

## Testing and delivery

- **Backend:** 2,100+ tests (JUnit 5, jqwik property tests, ArchUnit), run on H2 and on embedded PostgreSQL 18, so no
  Docker is needed. Golden files pin the fill model, P&L math, league stats and the JSON contract.
- **Frontend:** 375 Vitest unit tests and 19 Playwright spec files on phone, tablet and desktop viewports.
- **Contract:** the OpenAPI spec is generated from the code ([`docs/openapi.json`](docs/openapi.json)) and the
  frontend's TypeScript API types are generated from it, so the two can't drift apart.
- **CI/CD:** [GitHub Actions](.github/workflows/) build a `linux/amd64` + `linux/arm64` image on every push to `main`;
  Watchtower deploys it on the server. Backups and restores are in the [runbook](docs/runbook.md).

## Tech stack

| Layer | Tech |
| --- | --- |
| Backend | Java 21, Spring Boot 4.1 (Web MVC, Security, WebSocket/STOMP, Actuator), Spring AI MCP server, JdbcClient, Flyway, Caffeine, Bucket4j |
| Data | PostgreSQL 18 (H2 and embedded PostgreSQL for dev and tests) |
| Web | React 19, TypeScript, Vite, TanStack Router and Query, Tailwind CSS 4, TradingView Lightweight Charts, Workbox PWA with Web Push |
| AI | Model Context Protocol, OAuth 2.1 authorization server, Claude Code (headless), Anthropic and OpenAI SDKs |
| Market data | Alpaca (stocks, crypto, options; REST and WebSocket), Finnhub; a seeded simulator for dev and tests |
| Testing | JUnit 5, jqwik, ArchUnit, Vitest, Testing Library, Playwright; pandas for the strategy backtests |
| Infra | Docker, Docker Compose, GitHub Actions, GHCR, CasaOS, Watchtower, Cloudflare Tunnel |

## How I built it

I own the product, the architecture and quality:
- I decided what the league does and which brokerage rules it enforces.
- I chose the stack and how the pieces fit together, and I designed, reviewed and retuned the bots' strategies.
- I review and test every change, and I run the server it lives on.

The code was written with [Claude Code](https://claude.com/claude-code) as an AI pair programmer, working to my
direction; the commits carry its co-author line. Building it this way let one person ship a full brokerage
simulation, an MCP server and a fleet of bots in a few weeks.

## Repository layout

| Path | What |
| --- | --- |
| [`backend/`](backend/) | Spring Boot 4 / Java 21: API, trading engine, MCP server, Flyway migrations, tests |
| [`frontend/`](frontend/) | React + Vite web app and PWA, with Playwright end-to-end tests |
| [`tools/claude-trader/`](tools/claude-trader/) | Runs the Claude bots: scheduled headless Claude Code check-ins, one per AI player |
| [`tools/strategy-lab/`](tools/strategy-lab/) | The backtests behind the bots' strategies |
| [`tools/agent-runner/`](tools/agent-runner/) | An earlier bot runner on the Anthropic and OpenAI APIs (TypeScript) |
| [`deploy/`](deploy/) | Server setup, deploy and backup scripts |
| [`docs/`](docs/) | [Architecture spec](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), [deploy guide](docs/deploy.md), [runbook](docs/runbook.md), [bot guide](docs/agents.md), [player rules](docs/rules.md) |

## Running it locally

Needs JDK 21, Node 22.12+ and make. Docker isn't needed: the dev profile uses an H2 database and a simulated market,
so no API keys either.

```bash
make dev     # backend on :8080 and Vite on :5173, with demo players
make test    # backend tests (with architecture rules) and frontend unit tests
make e2e     # Playwright end to end
```

Then open <http://localhost:5173> and log in as `admin` / `admin-dev-123`. To click around the web app with no backend
at all, run `npm --prefix frontend run dev:mock`.

<sub>Paper money only: there is no brokerage connection, and nothing here is investment advice. The repository is
still named `stocks`, the project's working name.</sub>
