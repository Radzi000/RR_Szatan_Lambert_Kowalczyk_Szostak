# Strategy And Data Audit

## Scope

This report reviews the original QuantConnect-style reference strategies in [strategy_development/taken_strategies](/C:/Users/Rados/RR/strategy_development/taken_strategies), compares them with the current local implementation in [strategy_development/local_implementation](/C:/Users/Rados/RR/strategy_development/local_implementation), and proposes a practical next-step research design that preserves the existing deterministic Docker baseline.

Historical note:

- some later sections retain historical references to `intraday_momentum/`
- the current authoritative executable implementation is
  `strategy_development/local_implementation/`

Current reproducibility boundary:

- The existing local baseline is the Docker workflow documented in [README.md](/C:/Users/Rados/RR/README.md) and implemented by [strategy_development/local_implementation/reproduce.py](/C:/Users/Rados/RR/strategy_development/local_implementation/reproduce.py).
- It currently uses committed SPY daily and SPY 5-minute data only.
- It is fully local and should remain the primary reproducible path.
- QuantConnect should remain a reference and benchmark layer, not a required execution dependency.

## 1. What Are The 5 Strategies?

### Shared core logic across all five

All five reference files are single-asset intraday breakout strategies on SPY. They share these assumptions:

- Asset: `SPY` via `AddEquity("SPY", Resolution.Minute)`.
- Session model: US regular market hours, implicitly 9:30-16:00 Eastern.
- Intraday anchor variables:
  - today's open, set from the first usable bar around 9:31,
  - yesterday's close, recorded at market close,
  - minute-of-day volatility bands built from the average absolute move at the same clock minute over the prior 14 days.
- Position sizing: target daily volatility `vol_target = 0.02`, scaled by realized daily volatility from the last 14 daily returns, capped at leverage 2.
- Exit at end of day: near 15:58 or later, force liquidation.
- Long and short symmetry: go long above upper band, short below lower band.

### Strategy 0

File: [strategy_development/taken_strategies/strategy0.py](/C:/Users/Rados/RR/strategy_development/taken_strategies/strategy0.py)

Strategy name in file:
- `AccurateIntradayMomentum`

Original QuantConnect assumptions:
- Minute resolution SPY only.
- Uses QuantConnect VWAP indicator.
- Uses `Schedule.On(... BeforeMarketClose(..., 0), RecordEndOfDay)` to record close and reset state.
- Uses `SetHoldings` for fractional target exposure rather than explicit share sizing.

Traded asset(s):
- SPY only.

Required indicators:
- VWAP.
- 14-day realized daily volatility.
- Minute-of-day sigma profile from intraday absolute moves.

Required data fields:
- Intraday: `Open`, `Close`, `High`, `Low`, `Volume`.
- Daily: `Close` is strictly required for volatility targeting; full daily OHLCV is not necessary.

Required frequency/resolution:
- Minute intraday bars in the original implementation.
- Daily bars for volatility lookback warmup and sizing.

Entry logic:
- Every 30 minutes.
- Compute `upper_bound = max(today_open, yesterday_close) * (1 + sigma)`.
- Compute `lower_bound = min(today_open, yesterday_close) * (1 - sigma)`.
- Enter long if price breaks above upper bound.
- Enter short if price breaks below lower bound.

Exit logic:
- Every 30 minutes.
- If long, exit when price falls below `max(upper_bound, vwap)`.
- If short, exit when price rises above `min(lower_bound, vwap)`.
- Forced exit near market close.

Position sizing / volatility targeting:
- Daily returns deque of length 14.
- Leverage = `min(2, vol_target / std(daily_returns))`.

Risk management:
- Volatility targeting.
- Intraday VWAP/band trailing exit.
- End-of-day liquidation.

Special QuantConnect APIs or assumptions:
- `AddEquity`, `VWAP`, `SetWarmUp`, `Schedule.On`, `DateRules`, `TimeRules`, `SetHoldings`, `Liquidate`, `Portfolio`.

Parts that may not translate directly:
- QuantConnect VWAP is platform-provided and session-aware; local code must reconstruct session VWAP consistently.
- `SetHoldings` abstracts brokerage and share-quantity details; local backtests need explicit position and cost handling.
- QC minute bars and exchange calendar handling are vendor-specific.

### Strategy 1

File: [strategy_development/taken_strategies/strategy1.py](/C:/Users/Rados/RR/strategy_development/taken_strategies/strategy1.py)

Strategy name in file:
- `IntradayMomentum_1`

Original QuantConnect assumptions:
- Same as Strategy 0, but entry and exit are checked at different frequencies.

Traded asset(s):
- SPY only.

Required indicators:
- VWAP.
- 14-day realized daily volatility.
- Minute-of-day sigma profile.

Required data fields:
- Intraday OHLCV.
- Daily close.

Required frequency/resolution:
- Minute bars originally.
- Daily bars for volatility targeting.

Entry logic:
- Only every 30 minutes.
- Same breakout thresholds as Strategy 0.

Exit logic:
- Every 5 minutes.
- Exit long when price falls below `max(upper_bound, vwap)`.
- Exit short when price rises above `min(lower_bound, vwap)`.
- Forced exit near market close.

Position sizing / volatility targeting:
- Same as Strategy 0.

Risk management:
- Same as Strategy 0, but faster exits.

Special QuantConnect-specific assumptions:
- Same platform dependencies as Strategy 0.

Parts that may not translate directly:
- The 5-minute exit cadence is easy to reproduce with 1-minute or 5-minute data, but it does not map cleanly to 15-minute-only data.

### Strategy 2

File: [strategy_development/taken_strategies/strategy2.py](/C:/Users/Rados/RR/strategy_development/taken_strategies/strategy2.py)

Strategy name in file:
- `IntradayMomentum_2`

Original QuantConnect assumptions:
- Same SPY minute-resolution structure as Strategy 0.
- Adds an EMA trend filter.

Traded asset(s):
- SPY only.

Required indicators:
- VWAP.
- EMA(100) on minute data.
- 14-day realized daily volatility.
- Minute-of-day sigma profile.

Required data fields:
- Intraday OHLCV.
- Daily close.

Required frequency/resolution:
- Minute bars originally.
- Daily bars for volatility targeting.

Entry logic:
- Every 30 minutes.
- Long only if:
  - price > upper bound,
  - price > VWAP,
  - price > EMA(100).
- Short only if:
  - price < lower bound,
  - price < VWAP,
  - price < EMA(100).

Exit logic:
- Checked every 30 minutes in the reference file.
- Same band/VWAP exit as Strategy 0.
- Forced end-of-day liquidation.

Position sizing / volatility targeting:
- Same as Strategy 0.

Risk management:
- Volatility targeting.
- VWAP/band exit.
- Trend filter reduces entries in noisy/ranging regimes.

Special QuantConnect-specific assumptions:
- `EMA(self.spy_symbol, self.ema_period, Resolution.Minute)`.
- Indicator warmup and readiness handled by QC.

Parts that may not translate directly:
- EMA readiness/warmup needs explicit handling locally.
- With coarser bars, EMA(100) changes its time-scale substantially unless period is reinterpreted.

### Strategy 3

File: [strategy_development/taken_strategies/strategy3.py](/C:/Users/Rados/RR/strategy_development/taken_strategies/strategy3.py)

Strategy name in file:
- `AccurateIntradayMomentum`

Original QuantConnect assumptions:
- Same SPY minute-resolution structure as Strategy 1.
- Adds exit confirmation counters.

Traded asset(s):
- SPY only.

Required indicators:
- VWAP.
- 14-day realized daily volatility.
- Minute-of-day sigma profile.

Required data fields:
- Intraday OHLCV.
- Daily close.

Required frequency/resolution:
- Minute bars originally.
- Daily bars for volatility targeting.

Entry logic:
- Every 30 minutes.
- Same breakout entry as Strategy 0.

Exit logic:
- Check every 5 minutes.
- For long positions:
  - if price < `max(upper_bound, vwap)`, increment `long_exit_counter`,
  - else reset counter.
- For short positions:
  - if price > `min(lower_bound, vwap)`, increment `short_exit_counter`,
  - else reset counter.
- Exit only after 4 consecutive satisfied exit checks.
- Forced end-of-day liquidation.

Position sizing / volatility targeting:
- Same as Strategy 0.

Risk management:
- Volatility targeting.
- Exit smoothing via confirmation bars.
- End-of-day liquidation.

Special QuantConnect-specific assumptions:
- Same QC APIs as Strategy 0 and 1.

Parts that may not translate directly:
- Confirmation bars are tied to a 5-minute inspection grid. If the data is 15-minute-only, the temporal meaning changes materially.

### Strategy 4

File: [strategy_development/taken_strategies/strategy4.py](/C:/Users/Rados/RR/strategy_development/taken_strategies/strategy4.py)

Strategy name in file:
- `IntradayMomentum_4`

Original QuantConnect assumptions:
- Combination of Strategy 2 and Strategy 3.
- Same SPY minute-resolution environment.

Traded asset(s):
- SPY only.

Required indicators:
- VWAP.
- EMA(100).
- 14-day realized daily volatility.
- Minute-of-day sigma profile.

Required data fields:
- Intraday OHLCV.
- Daily close.

Required frequency/resolution:
- Minute bars originally.
- Daily bars for volatility targeting.

Entry logic:
- Every 30 minutes.
- Long if price > upper bound and price > EMA.
- Short if price < lower bound and price < EMA.
- The code comment says dual confirmation with EMA; unlike Strategy 2, the actual code does not require `price > VWAP` for entry.

Exit logic:
- Every 5 minutes with 4-bar confirmation.
- Exit threshold still depends on band and VWAP.
- Forced end-of-day liquidation.

Position sizing / volatility targeting:
- Same as Strategy 0.

Risk management:
- Volatility targeting.
- EMA direction filter.
- Confirmed exits.
- Forced flat at close.

Special QuantConnect-specific assumptions:
- Same QC APIs as the earlier strategies.

Parts that may not translate directly:
- Same as Strategy 2 and 3 combined.
- The file uses a different date window from the others, which looks more like a test window than a design requirement.

## 2. What Data Does Each Strategy Require?

### Shared minimum data requirements

All five strategies require:

- Daily close series for realized volatility targeting.
- Intraday OHLCV bars.
- A session calendar or an equivalent way to identify:
  - first tradable bar of the day,
  - end-of-day liquidation time,
  - per-session resets.

Close-only is not sufficient because:

- today's open is used,
- VWAP needs price and volume,
- local VWAP approximation uses `High`, `Low`, `Close`, `Volume`,
- session logic depends on intraday bar timestamps.

### By strategy

| Strategy | OHLCV needed | Daily data needed | Intraday data needed | VWAP needed | Volume needed | Session calendar needed | Warmup / lookback | 15-minute validity |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Strategy0 | Yes | Yes | Yes | Yes | Yes | Yes | 14 daily returns and 14 session histories per minute slot | Weak for faithful reproduction, acceptable only as adapted extension |
| Strategy1 | Yes | Yes | Yes | Yes | Yes | Yes | Same as S0 | Weaker, because 5-minute exit cadence is lost |
| Strategy2 | Yes | Yes | Yes | Yes | Yes | Yes | Same as S0 plus EMA(100) warmup | Acceptable only with explicit EMA/interval reinterpretation |
| Strategy3 | Yes | Yes | Yes | Yes | Yes | Yes | Same as S1 plus 4 exit confirmations | Weak for faithful reproduction, possible only as adapted extension |
| Strategy4 | Yes | Yes | Yes | Yes | Yes | Yes | Same as S2 and S3 | Same caveat as S3 plus EMA scaling issue |

### VWAP detail

VWAP is required in all five strategies.

- In QuantConnect it is a platform indicator.
- In local Python it can be approximated from intraday bars using cumulative price-volume calculations.
- If only close and volume are available, an approximate close-based VWAP is possible, but the local implementation currently uses typical price from `High`, `Low`, and `Close`, which is better.

### Market-hours assumptions

The strategies are not 24/7-native. They assume:

- a clear market open,
- a meaningful previous close,
- an end-of-session flattening event,
- stable minute-of-day seasonality.

That fits US equities and ETFs best. It is less natural for crypto unless sessions are imposed artificially.

### Whether 15-minute bars are valid

Strictly speaking, 15-minute bars are not a faithful reproduction of the original strategies because:

- the original uses minute-of-day sigma keyed by exact minute,
- today's open is captured from the first usable minute bar,
- Strategy 1, 3, and 4 require 5-minute exit checks,
- all strategies force liquidation at 15:58+, which is not representable with coarse 15-minute bars.

15-minute bars are valid only as an adapted extension, not as an exact replica.

## 3. What Frequencies Are Plausible?

### 1 minute

Preserves original logic:
- Yes, best match to the original reference.

Changes needed:
- None beyond local implementation details.

Pros:
- Most faithful to original QC logic.
- Preserves 9:31 open logic, 5-minute exit cadence, 30-minute entry cadence, 15:58 forced exit.

Cons:
- Highest data burden.
- More fragile for multi-asset reproducibility if data must be committed.

Risk of distortion:
- Lowest.

Computational burden:
- Highest.

### 2 minute

Preserves original logic:
- Partially.

Changes needed:
- 30-minute entries still translate naturally as every 15 bars.
- 5-minute exits do not translate exactly.
- EOD liquidation timing and first usable bar assumptions become approximate.

Pros:
- Much lighter than 1-minute data.
- Still captures intraday structure reasonably well.

Cons:
- Exit cadence mismatch.
- Minute-of-day sigma loses some fidelity.

Risk of distortion:
- Moderate.

Computational burden:
- Medium-high.

### 5 minute

Preserves original logic:
- Reasonably well for a pragmatic local reproduction baseline.

Changes needed:
- 30-minute entries become every 6 bars.
- 5-minute exits map naturally to every bar.
- 15:58 forced exit becomes approximate because the exact close may not align perfectly with the bar grid.
- Minute-of-day sigma is coarser but still session-aware.

Pros:
- Best tradeoff between fidelity and reproducibility.
- Small enough to commit for class grading.
- Already used by the current deterministic baseline.

Cons:
- Opening-bar semantics are slightly coarser than 1-minute data.
- Some microstructure effects are lost.

Risk of distortion:
- Low to moderate.

Computational burden:
- Moderate.

### 15 minute

Preserves original logic:
- No, not as a strict reproduction.

Changes needed:

- Strategy 0:
  - 30-minute entries can be redefined as every 2 bars.
  - Exit checks also become every 2 bars if kept symmetric, or every bar if more reactive behavior is desired.
- Strategy 1:
  - 30-minute entry becomes every 2 bars.
  - 5-minute exit cannot be preserved; the cleanest adaptation is exit every bar.
- Strategy 2:
  - Same interval adaptation as Strategy 0.
  - EMA(100) at 15-minute bars represents a much longer real-time horizon than EMA(100) at 1-minute bars.
  - To preserve rough wall-clock behavior, an EMA around 7 bars would be closer to 100 minutes; to preserve bar-count behavior, keep 100 and accept that the strategy meaning changes.
- Strategy 3:
  - 4 exit confirmations every 5 minutes equals 20 minutes in the original.
  - On 15-minute bars, either:
    - use 2 confirmation bars, which becomes 30 minutes,
    - or use 1 confirmation bar, which becomes 15 minutes.
  - Neither is equivalent.
- Strategy 4:
  - Same issues as Strategy 3 plus EMA time-scale reinterpretation.

Pros:
- Much easier to maintain across many assets.
- Lower storage burden.
- Better fit for a class project that emphasizes reproducibility over microstructure precision.

Cons:
- Meaningful departure from original logic.
- Session-open and 5-minute exit mechanics are no longer preserved.
- Confirmation timing changes materially.

Risk of distortion:
- High if presented as a direct reproduction.
- Acceptable if explicitly presented as a coarser extension experiment.

Computational burden:
- Low.

### 30 minute

Preserves original logic:
- Poorly.

Changes needed:
- Entries become every bar.
- 5-minute exits disappear entirely.
- VWAP/band logic becomes much less reactive.

Pros:
- Very lightweight.

Cons:
- Too coarse for the stated strategy family.

Risk of distortion:
- Very high.

Computational burden:
- Very low.

### Daily / intraday hybrid

Preserves original logic:
- This is already part of the original design.

Changes needed:
- None conceptually; daily is for sizing, intraday is for signals.

Pros:
- Clean design.
- Daily realized volatility targeting is reasonable across asset classes.

Cons:
- Requires careful alignment of daily and intraday calendars.

Risk of distortion:
- Low if done carefully.

Computational burden:
- Moderate.

### Recommendation on 15-minute frequency

15-minute bars are acceptable for the extension phase only if documented as an adapted version of the original strategy family, not as an exact reproduction.

Practical recommendation:

- Keep the current 5-minute SPY pipeline as the local reproduction benchmark.
- Use 15-minute bars for the broader cross-asset extension because they reduce data burden and are more manageable for equities, commodity ETFs, and crypto.
- Explicitly define the 15-minute adaptation as:
  - entry interval: 30 minutes becomes every 2 bars,
  - exit interval: 5 minutes becomes every 1 bar,
  - exit confirmation: 4 x 5-minute checks becomes 2 x 15-minute checks if you want a conservative analogue,
  - EMA: either keep `ema_period=100` as a bar-based design choice, or rescale to preserve approximate wall-clock meaning. If reproducibility and simplicity matter more than exact time-scale equivalence, keep the same parameter and state clearly that it is a coarser extension.

## 4. What Asset Classes Are Plausible?

### US equities

Does the logic make sense:
- Yes, strongly.

Required modifications:
- Minimal.

Data requirements:
- Regular-session intraday OHLCV and daily close.

Session/calendar issues:
- Best fit, because the strategy depends on open, close, and previous close.

Liquidity/slippage:
- Use liquid large-cap equities or ETFs; avoid small caps.

Volatility targeting:
- Reasonable with daily returns.

Overnight gaps:
- Central to the design and naturally handled via previous close vs today's open.

24/7 issue:
- None.

Assessment:
- Plausible, but ETFs are cleaner than single stocks because they reduce idiosyncratic news risk and survivorship concerns.

### Equity ETFs

Does the logic make sense:
- Yes, best fit overall.

Required modifications:
- Minimal.

Data requirements:
- Same as US equities.

Session/calendar issues:
- Clean.

Liquidity/slippage:
- Usually excellent for major ETFs.

Volatility targeting:
- Stable and comparable across assets.

Overnight gaps:
- Meaningful and aligned with the original logic.

24/7 issue:
- None.

Assessment:
- Best primary asset class for the project.

### Commodity ETFs

Does the logic make sense:
- Yes, but as a proxy, not as a direct commodity market strategy.

Required modifications:
- Minimal if treated as US exchange-traded instruments.

Data requirements:
- Same as equity ETFs.

Session/calendar issues:
- Clean if using ETF market hours.

Liquidity/slippage:
- Good for GLD and SLV.
- USO and UNG require more caution due to roll and structural distortions.

Volatility targeting:
- Often requires no formula change, but can produce larger leverage swings.

Overnight gaps:
- Still meaningful.

24/7 issue:
- None.

Assessment:
- Good secondary asset class if you use liquid ETF proxies and explain that they represent exchange-traded commodity exposure, not direct futures execution.

### Futures or futures proxies

Does the logic make sense:
- Futures themselves are less aligned with the original regular-session equity logic because many contracts trade extended hours.
- Futures proxies via ETFs make more sense for this course.

Required modifications:
- If using actual futures, session definitions must be rewritten.

Data requirements:
- Much stricter and harder to keep deterministic and clean.

Session/calendar issues:
- Significant.

Liquidity/slippage:
- Contract-roll handling is required.

Volatility targeting:
- Fine mathematically, but operationally more complex.

Assessment:
- Avoid actual futures in the main project unless you already have high-quality deterministic continuous-contract data and explicit roll logic.

### Crypto spot/perpetuals

Does the logic make sense:
- Partially.

Required modifications:
- You must impose an artificial session boundary if you want to preserve:
  - today open,
  - yesterday close,
  - end-of-day flattening,
  - minute-of-day seasonality.
- UTC-based midnight sessions or US/Eastern daily sessions are possible, but the choice must be fixed and justified.

Data requirements:
- Intraday OHLCV and daily closes from the same session convention.

Session/calendar issues:
- Major difference from equities because crypto trades 24/7.

Liquidity/slippage:
- BTC and ETH are fine.
- Smaller coins are noisier and venue-specific.

Volatility targeting:
- Needs tighter leverage caps or lower `vol_target` because crypto realized vol is much higher.

Overnight gaps:
- Less meaningful under continuous trading.

24/7 issue:
- This is the biggest conceptual mismatch.

Assessment:
- Plausible as an extension if framed carefully as a session-imposed adaptation, not a pure port of the original QC equity logic.

### FX

Does the logic make sense:
- Only weakly.

Required modifications:
- Like crypto, FX is nearly continuous.
- Session boundaries are less natural for this strategy family.

Assessment:
- Lower priority than equity ETFs, commodity ETFs, and crypto.

## 5. Which Concrete Assets Should We Use?

### General view on the candidate list

The suggested lists are directionally good, but they should be trimmed.

What looks good:

- Equity ETFs:
  - SPY, QQQ, IWM are strong choices.
  - DIA is acceptable but somewhat redundant with SPY.
- Sector ETFs:
  - XLK, XLF, XLE are useful because they introduce different regimes.
  - XLY, XLP, XLV, XLI, XLU are fine, but the full set may be too broad for a class project.
- Commodity ETFs:
  - GLD and SLV are good.
  - DBC is a cleaner broad commodity proxy than some niche instruments.
  - USO is usable but structurally idiosyncratic.
  - UNG is high-risk from a methodology perspective because it is heavily affected by roll and storage dynamics.
  - DBA is acceptable but less central.
- Crypto:
  - BTCUSDT and ETHUSDT are strong choices.
  - SOLUSDT is a reasonable third crypto.
  - BNBUSDT and XRPUSDT are less necessary for a compact reproducible project.

### Minimal universe for reproducibility and debugging

Recommended:

- SPY
- GLD
- BTCUSDT

Why:

- Three distinct regimes: equity index, commodity proxy, crypto.
- Small enough for deterministic debugging and quick offline validation.
- Easy to explain in the final report.

### Medium universe for final research

Recommended:

- Equity ETFs:
  - SPY
  - QQQ
  - IWM
  - XLK
  - XLE
- Commodity ETFs:
  - GLD
  - SLV
  - DBC
- Crypto:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT

Why:

- Good cross-section without becoming too large.
- Covers broad equity beta, growth/tech, small caps, energy, precious metals, diversified commodity exposure, and crypto.
- Still realistic to commit and run reproducibly on 15-minute data if file sizes stay controlled.

### Ambitious universe if time allows

Recommended:

- Equity ETFs:
  - SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV
- Commodity ETFs:
  - GLD, SLV, DBC, USO
- Crypto:
  - BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT

Why:

- Adds more breadth, but still avoids the weakest candidates.

Not recommended unless well-justified:

- UNG as a core research asset.
- A large full sector basket if you are short on time.
- Too many lower-liquidity crypto names.

### Preferred final choice

Given the current repo and the preference for 15-minute data:

- Best balanced final universe:
  - SPY, QQQ, IWM, XLK, XLE
  - GLD, SLV, DBC
  - BTCUSDT, ETHUSDT, SOLUSDT
- Preferred frequency for the extension layer:
  - 15-minute
- Preferred benchmark frequency for the reproduction layer:
  - 5-minute SPY

## 6. Recommended Final Research Design

### Core design

Use a two-layer design:

- Layer 1: local reproduction benchmark
  - Current committed SPY daily plus SPY 5-minute data.
  - Reproduce all five local strategies deterministically.
- Layer 2: extension study
  - Multi-asset universe.
  - Prefer 15-minute bars for scale and practicality.
  - Explicitly document that this is a coarser extension, not a strict one-minute replica.

### Data frequency

Recommended:

- Reproduction benchmark: 5-minute intraday plus daily sizing data.
- Extension research: 15-minute intraday plus daily sizing data.

### Asset universe

Recommended medium final universe:

- Equities and sector ETFs:
  - SPY, QQQ, IWM, XLK, XLE
- Commodity ETFs:
  - GLD, SLV, DBC
- Crypto:
  - BTCUSDT, ETHUSDT, SOLUSDT

### Train / validation / test split

Use one global time split across all assets:

- Train: first 70%
- Validation: next 15%
- Test: final 15%

Important:

- Split by time, not by random shuffling.
- Use identical date boundaries across all assets within an asset class and ideally globally.
- Parameter search must see only train data.
- Model/parameter selection must use only validation.
- Test must remain untouched until the final comparison.

### Baseline strategy set

- Strategy0 through Strategy4, using the local Python implementation.

### Parameter optimization plan

- Optimizers:
  - CMA-ES
  - NES if implemented later
- Primary optimization objective:
  - Sharpe ratio on train
- Suggested secondary constraints:
  - minimum number of trades,
  - max drawdown ceiling,
  - turnover sanity check.

### Validation selection protocol

- For each strategy and asset:
  - optimize parameters on train only,
  - evaluate all candidate solutions on validation,
  - pick the parameter set with best validation Sharpe,
  - break ties using lower drawdown or higher trade count robustness.

### OOS evaluation protocol

Compare on test only:

- original local baseline parameters,
- tuned local parameters,
- regime-aware or seasonality-aware local variants,
- portfolio combinations built from test-period signals only after selection is frozen.

### Portfolio construction protocol

Build final test-period portfolios from selected strategy-asset combinations:

- Equal weight
- Kelly-style weighting
  - use fractional Kelly, not full Kelly
  - estimate from train/validation statistics only
- Markowitz mean-variance
  - use regularization and turnover controls
  - estimate covariance from train or train+validation, never from test

### Metrics

At minimum report:

- total return
- annualized return
- annualized volatility
- Sharpe ratio
- Sortino ratio if easy
- max drawdown
- Calmar ratio
- hit rate
- turnover
- number of trades
- average trade PnL
- exposure / time in market

Also useful:

- median trade PnL
- profit factor
- long vs short decomposition
- per-asset contribution

## 7. QuantConnect Reference Design

### How QuantConnect should be included

QuantConnect should be included as an external reference and benchmark only.

### Answers to the key questions

Should original QC code be preserved:
- Yes. Keep the five original copied files under `strategy_development/taken_strategies`.

Should we include QC-ready project folders:
- Yes, optionally. This is useful if you want a clean reference artifact for QC or Lean users.

Should we include public QC backtest links:
- Yes, if available. They are a strong transparency artifact.

Should exported QC metrics be committed:
- Yes. Static exported summary statistics are valuable because public links may disappear or require sign-in later.

Should Docker call QuantConnect:
- No.
- Reason:
  - it would introduce account dependency,
  - it would require internet,
  - it would make reproduction depend on a third-party cloud platform,
  - it would violate the clean local reproducibility story.

Are public QC result links enough for the course:
- Not on their own.
- They are useful as external reference evidence, but not sufficient for the primary reproducibility requirement because they are not locally rerunnable and may rot.

How README should describe the distinction:

- Local reproducible results:
  - generated by Docker,
  - deterministic,
  - committed data only,
  - no QC dependency.
- QuantConnect reference results:
  - external benchmark,
  - used to show correspondence or sanity-check behavior,
  - not required to reproduce the local project outputs.

### Recommended future files

Suggested future structure:

```text
strategy_development/
  taken_strategies/
  quantconnect_reference/
    README.md
    projects/
    results/
      quantconnect_backtest_links.md
      exported_statistics.csv
```

### What should be in `quantconnect_backtest_links.md`

For each strategy:

- strategy file name
- QuantConnect project name
- public backtest URL
- backtest date exported
- QC data resolution
- QC universe / asset
- short note on what the link represents
- warning that this is external reference material, not the primary reproducible workflow

### What should be in `exported_statistics.csv`

Columns should include at least:

- strategy_id
- strategy_name
- platform
- asset
- resolution
- start_date
- end_date
- total_return
- annual_return
- sharpe
- sortino if available
- max_drawdown
- trades
- win_rate
- notes

## 8. What Should Be The Final Project Story?

Recommended README/report narrative:

This project starts from five intraday momentum strategies originally written for QuantConnect. QuantConnect provided the original execution environment, market calendar handling, and platform indicators, but a cloud-only backtest is not sufficient for a Reproducible Research course because a grader must be able to rerun the workflow locally, deterministically, and without relying on external accounts or live data downloads.

The project therefore has two layers.

First, it preserves the original QuantConnect implementations as reference artifacts so the original algorithmic intent is transparent. Second, it reimplements the strategy logic locally in Python and runs it in Docker on committed offline data. This local layer is the authoritative reproducible workflow.

The project then extends the original SPY-focused setup in a controlled way by testing the same strategy family on a small cross-asset universe, using train/validation/test splits, parameter tuning, and trade-dependency analysis. QuantConnect public links and exported statistics can be included as benchmark references, but they are supplementary evidence rather than required execution dependencies.

The key comparison is not only whether the original logic can be copied, but whether it can be reproduced locally, stress-tested across assets and frequencies, tuned without leakage, and combined into final out-of-sample portfolios in a way that another investigator can rerun from the repository alone.

## 9. What Is Unclear Or Risky?

- Original strategy assumptions may be underspecified:
  - the code implies session logic, but not every design decision is documented.
- Data mismatch:
  - the current deterministic baseline is SPY 5-minute only,
  - the broader cross-asset extension will need new committed datasets.
- Frequency mismatch:
  - 15-minute bars are an adaptation, not a direct reproduction.
- QuantConnect-specific behavior:
  - indicator definitions,
  - order fill assumptions,
  - session handling,
  - warmup semantics.
- Transaction costs and slippage:
  - current local backtest uses simple commission logic and no detailed slippage model.
- Calendar/session handling:
  - especially important when mixing equities and crypto.
- Overfitting risk:
  - NES and CMA-ES can easily overfit if validation is not used strictly.
- Look-ahead bias:
  - especially if daily and intraday timestamps are not aligned carefully.
- Survivorship bias:
  - ETF universes are safer than individual equities, but still need documentation.
- Vendor inconsistencies:
  - Yahoo-derived local files will not exactly match QuantConnect data.
- Crypto 24/7 mismatch:
  - artificial sessionization may change the economics of the strategy.
- QuantConnect cloud reproducibility limitations:
  - public links may break,
  - exports may not be perfectly versioned,
  - results depend on account/platform state.
- Public link rot:
  - reinforces the need for committed exported statistics.

## 10. Recommended Repo Structure After Future Cleanup

Do not implement this yet, but this is a clean target:

```text
data/
  raw/
  processed/
  README.md

preprocessing/
  __init__.py
  calendars.py
  resample.py
  splits.py
  quality_checks.py

intraday_momentum/
  data/
  strategies/
  backtest/
  optimization/
  visualization/
  reproduce.py

strategy_development/
  taken_strategies/
  quantconnect_reference/
    README.md
    projects/
    results/
      quantconnect_backtest_links.md
      exported_statistics.csv
  local_strategies/
    README.md

trade_dependency/
  regimes/
  seasonality/
  dependency_analysis/

final_portfolio/
  allocation/
  portfolio_backtests/
  reporting/

outputs/
  tables/
  figures/
  report/

tests/
docs/
Dockerfile
docker-compose.yml
Makefile
README.md
AI_USAGE.md
```

Important recommendation:

- Keep [intraday_momentum](/C:/Users/Rados/RR/intraday_momentum) as the installable package and the main local implementation.
- Do not move it under `strategy_development/local_strategies` if avoiding breakage is important.
- Use `strategy_development` for reference and research-support material, not for the primary production package.

## 11. Cleanup Recommendations

### Essential

- `intraday_momentum/`
- `data/`
- `outputs/`
- `tests/`
- `docs/`
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `README.md`
- `AI_USAGE.md`

### Should remain for reference

- `strategy_development/taken_strategies/`
  - keep as immutable upstream-style reference material

### Should be added later

- `strategy_development/quantconnect_reference/`
- more explicit preprocessing modules
- trade-dependency analysis modules
- portfolio construction modules

### Should probably be moved or formalized later

- `strategy_development/our_strategies/`
  - currently empty and ambiguous
  - either rename, remove, or replace with a clearly documented purpose

### Currently empty or placeholder areas

- `trade_dependency/`
- `final_portfolio/`

These should either:

- become real modules in the next phase,
- or remain clearly marked as planned future work.

### Should not be moved casually

- `intraday_momentum/`

Reason:

- It already anchors the reproducible Docker workflow.
- Moving it into a research subdirectory would create packaging and path churn for little benefit.

## 12. Reproducibility Constraints For Any Future Refactor

The following must remain true during any cleanup or extension work:

- `docker compose up --build reproduce` must continue to work.
- The main local pipeline must remain fully offline.
- No live downloads in the final reproduction path.
- All final data must be committed or derived deterministically from committed inputs, with checksums.
- Random seeds must be fixed where relevant.
- No manual notebook execution for grading.
- Outputs must be regenerated automatically into stable locations.
- Tests must pass locally and in Docker.
- README and docs must distinguish clearly between:
  - local reproducible results,
  - external QuantConnect reference results.
- QuantConnect must never become a required dependency for reproducing the local results.

## Bottom-Line Recommendations

### On frequencies

- For faithful reproduction: keep 5-minute or finer.
- For the broader cross-asset extension: 15-minute is acceptable if explicitly presented as an adapted version of the strategy family.

### On assets

- Best overall asset class: liquid US ETFs.
- Best secondary class: liquid commodity ETFs.
- Best optional third class: large-cap crypto with explicit sessionization.

### On project design

- Preserve the original QC files.
- Keep Docker and local Python as the authoritative reproducible layer.
- Use QuantConnect as benchmark documentation only.
- Treat 5-minute SPY as the reproducible benchmark and 15-minute cross-asset experiments as the extension layer.
