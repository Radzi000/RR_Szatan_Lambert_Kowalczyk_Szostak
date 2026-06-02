# Actual Strategy Logic Audit

This audit is based on the implementation code, not on README descriptions. The
local strategy code lives under `strategy_development/local_implementation/`;
the reference QuantConnect-style files live under
`strategy_development/taken_strategies/`.

## 1. Executive summary

The five local strategies are intraday momentum breakout strategies. All five
trade breakouts beyond minute-of-day sigma bands built around the larger of
today's open and yesterday's close on the upside, and the smaller of today's
open and yesterday's close on the downside.

Common implementation pattern:

- Each class implements `generate_signals(daily_data, minute_data)` and returns
  a chronological list of `Signal` objects from
  `strategy_development/local_implementation/strategies/base.py`.
- Input data is expected in QuantConnect-like column format:
  `Open`, `High`, `Low`, `Close`, `Volume`, indexed by timestamp.
- Today's open is captured on the first bar satisfying
  `BaseStrategy._is_market_open(hour, minute)`, implemented as hour `9` and
  minute `<= 31`.
- Yesterday's close is updated to the last `Close` in each grouped session.
- The signal threshold uses a per-time-key sigma:
  `mean(last lookback absolute moves for that HH:MM)`.
- The intraday move stored for sigma is
  `abs(current_price / todays_open - 1)`.
- Dynamic leverage is `min(2.0, vol_target / std(recent_daily_returns))`.
- Long entries use direction `1`; short entries use direction `-1`; exits use
  direction `0`.
- All five force an end-of-day exit when
  `BaseStrategy._is_market_close(hour, minute)` is true, implemented as hour
  `15` and minute `>= 58`.
- All five can trade both long and short.
- Strategy classes do not charge transaction costs. Costs are charged by
  `BacktestEngine` in
  `strategy_development/local_implementation/backtest/engine.py`, using
  `TransactionCostConfig` from
  `strategy_development/local_implementation/costs.py`.

What differs:

- Strategy0 checks entries and exits on one interval.
- Strategy1 separates entry and exit check intervals.
- Strategy2 adds EMA and VWAP confirmation to entries.
- Strategy3 adds consecutive exit confirmation counters.
- Strategy4 combines EMA-filtered entries with confirmed exits.

Important code-observed caveat:

- In every local strategy class, `daily_returns` is computed once from the full
  `daily_data` passed to `generate_signals`, and each bar uses
  `daily_returns[-lookback:]`. This is not a rolling volatility window through
  the current timestamp. It means leverage is based on the last `lookback`
  daily returns of the full input frame for every bar in that run.

How the local implementation differs from the original reference:

- The reference files are QuantConnect `QCAlgorithm` classes using
  `AddEquity("SPY", Resolution.Minute)`, `VWAP`, `EMA`, `Schedule.On`,
  `SetWarmUp`, `SetHoldings`, `Liquidate`, and `Portfolio` state.
- The local files are framework-free Python classes that generate signals. A
  separate local backtester turns those signals into positions, trades, equity,
  turnover, and cost-aware metrics.
- The reference strategies are SPY minute strategies. The fixed local runner
  applies the same strategy classes to processed 15-minute cross-asset data,
  including equities, commodities, and crypto, after converting normalized
  OHLCV columns into `Open`, `High`, `Low`, `Close`, `Volume`.
- The local code removes live QuantConnect data, scheduling, brokerage, and
  portfolio APIs from the reproduction path.

## 2. Strategy-by-strategy explanation

### Strategy0 / Baseline

- File path: `strategy_development/local_implementation/strategies/strategy0.py`
- Class name: `Strategy0`
- Display name: `Strategy0 / Baseline` in
  `strategy_development/local_implementation/strategy_specs.py`
- Defaults from constructor: `lookback=14`, `vol_target=0.02`,
  `entry_interval=30`
- Fixed spec params: `{"lookback": 14, "vol_target": 0.02}`
- Required input data: `daily_data["Close"]`; `minute_data` with `Open`,
  `High`, `Low`, `Close`, and normally `Volume`
- Indicators used: minute-of-day sigma bands; intraday VWAP computed from
  typical price `(High + Low + Close) / 3` times `Volume`; realized daily
  volatility from daily close returns
- Entry rules:
  - Only after today's open and yesterday's close are known.
  - Only if there are at least `lookback` daily returns and sigma is nonzero.
  - Checked when `minute % entry_interval == 0`.
  - Long if `current_price > upper_bound`.
  - Short if `current_price < lower_bound`.
  - `upper_bound = max(todays_open, yesterdays_close) * (1 + sigma)`.
  - `lower_bound = min(todays_open, yesterdays_close) * (1 - sigma)`.
- Exit rules:
  - Forced flat signal at hour `15`, minute `>= 58`.
  - On the same interval as entries, long exits when
    `current_price < max(upper_bound, vwap_val)`.
  - Short exits when `current_price > min(lower_bound, vwap_val)`.
- Position sizing:
  - Entry signal leverage is `calculate_dynamic_leverage(recent_returns)`.
  - In `BaseStrategy`, this is capped at `2.0`.
  - The code passes leverage on entries and uses `direction=0` on exits.
- Risk controls:
  - Volatility-scaled leverage cap.
  - Exit threshold tied to VWAP and sigma band.
  - End-of-day forced exit.
- Session handling:
  - `minute_data` is grouped by `minute_data.index.date`.
  - Today's open is the first bar at 9:00 or 9:31 according to
    `_is_market_open`; in normal equity data this is intended to catch 9:31.
  - The position variable is maintained across grouped days but is reset by EOD
    exits when those timestamps are present.
- Transaction-cost handling:
  - None inside `Strategy0`; handled by `BacktestEngine`.
- Directionality: long and short.
- EMA/VWAP/sigma/vol/confirmation:
  - Uses sigma bands, VWAP exits, volatility targeting.
  - Does not use EMA.
  - Does not use confirmation counters.
- Difference relative to previous strategy: not applicable; this is the base.

### Strategy1 / Asymmetric Intervals

- File path: `strategy_development/local_implementation/strategies/strategy1.py`
- Class name: `Strategy1`
- Display name: `Strategy1 / Asymmetric Intervals`
- Defaults: `lookback=14`, `vol_target=0.02`, `entry_interval=30`,
  `exit_interval=5`
- Fixed spec params: `{"lookback": 14, "vol_target": 0.02,
  "entry_interval": 30, "exit_interval": 5}`
- Required input data: same as Strategy0.
- Indicators used: same sigma bands, same locally computed VWAP, same daily
  return volatility sizing.
- Entry rules:
  - Same breakout rules as Strategy0.
  - Checked only when flat and `minute % entry_interval == 0`.
- Exit rules:
  - Forced EOD exit at hour `15`, minute `>= 58`.
  - If invested, exit logic is checked when `minute % exit_interval == 0`.
  - Long exit: `current_price < max(upper_bound, vwap_val)`.
  - Short exit: `current_price > min(lower_bound, vwap_val)`.
- Position sizing: same dynamic leverage as Strategy0.
- Risk controls: same as Strategy0, but exit checks are more frequent by
  default.
- Session handling: same grouped-date logic as Strategy0.
- Transaction-cost handling: none in strategy class; handled by
  `BacktestEngine`.
- Directionality: long and short.
- EMA/VWAP/sigma/vol/confirmation:
  - Uses sigma bands, VWAP exits, volatility targeting.
  - Does not use EMA.
  - Does not use confirmation counters.
- Exact differences relative to Strategy0:
  - Adds `exit_interval`.
  - Exit checks are independent from entry checks.
  - Default entries remain every 30 minutes; default exits are every 5 minutes.

### Strategy2 / EMA Filter

- File path: `strategy_development/local_implementation/strategies/strategy2.py`
- Class name: `Strategy2`
- Display name: `Strategy2 / EMA Filter`
- Defaults: `lookback=14`, `vol_target=0.02`, `entry_interval=30`,
  `ema_period=100`
- Fixed spec params: `{"lookback": 14, "vol_target": 0.02,
  "entry_interval": 30, "ema_period": 100}`
- Required input data: same as Strategy0, with `Close` required for EMA.
- Indicators used:
  - Sigma bands.
  - Locally computed VWAP.
  - EMA from `minute_data["Close"].ewm(span=ema_period, adjust=False).mean()`.
  - Daily return volatility sizing.
- Entry rules:
  - Checked when `minute % entry_interval == 0`.
  - Long requires all of:
    `current_price > upper_bound`, `current_price > vwap_val`,
    `current_price > ema_val`.
  - Short requires all of:
    `current_price < lower_bound`, `current_price < vwap_val`,
    `current_price < ema_val`.
- Exit rules:
  - Same interval structure as Strategy0, not Strategy1.
  - Forced EOD exit at hour `15`, minute `>= 58`.
  - Long exit when `current_price < max(upper_bound, vwap_val)`.
  - Short exit when `current_price > min(lower_bound, vwap_val)`.
- Position sizing: same dynamic leverage as Strategy0.
- Risk controls: same as Strategy0 plus EMA and VWAP entry confirmation.
- Session handling: same grouped-date logic as Strategy0.
- Transaction-cost handling: none in strategy class; handled by
  `BacktestEngine`.
- Directionality: long and short.
- EMA/VWAP/sigma/vol/confirmation:
  - Uses sigma bands, VWAP, EMA, volatility targeting.
  - Does not use confirmation counters.
- Exact differences relative to Strategy1:
  - Removes separate `exit_interval`; exits occur only inside the
    `entry_interval` block.
  - Adds `ema_period`.
  - Adds EMA and VWAP filters to entries.
  - Strategy2 entry confirmation is stricter than Strategy1, but exit timing is
    less frequent by default because there is no separate 5-minute exit loop.

### Strategy3 / Exit Confirmation

- File path: `strategy_development/local_implementation/strategies/strategy3.py`
- Class name: `Strategy3`
- Display name: `Strategy3 / Exit Confirmation`
- Defaults: `lookback=14`, `vol_target=0.02`, `entry_interval=30`,
  `exit_interval=5`, `exit_confirmation_bars=4`
- Fixed spec params: `{"lookback": 14, "vol_target": 0.02,
  "entry_interval": 30, "exit_interval": 5,
  "exit_confirmation_bars": 4}`
- Required input data: same as Strategy0.
- Indicators used: sigma bands, locally computed VWAP, daily return volatility
  sizing.
- Entry rules:
  - Same breakout rules as Strategy1.
  - Checked only when flat and `minute % entry_interval == 0`.
  - Counters are reset on entry.
- Exit rules:
  - Forced EOD exit at hour `15`, minute `>= 58`; counters reset.
  - Exit checks occur when invested and `minute % exit_interval == 0`.
  - For a long, the exit condition is
    `current_price < max(upper_bound, vwap_val)`.
  - For a short, the exit condition is
    `current_price > min(lower_bound, vwap_val)`.
  - The relevant counter increments only while the exit condition is true.
  - The relevant counter resets to zero when the condition is false.
  - Liquidation happens only when the counter reaches
    `exit_confirmation_bars`.
- Position sizing: same dynamic leverage as Strategy0.
- Risk controls:
  - Same as Strategy1 plus confirmed exits.
  - Confirmation can delay exits versus Strategy1.
- Session handling:
  - Same grouped-date logic as Strategy0.
  - `long_exit_counter` and `short_exit_counter` reset at the start of each
    grouped day, on EOD exit, and after confirmed exits or new entries.
- Transaction-cost handling: none in strategy class; handled by
  `BacktestEngine`.
- Directionality: long and short.
- EMA/VWAP/sigma/vol/confirmation:
  - Uses sigma bands, VWAP exits, volatility targeting, confirmation counters.
  - Does not use EMA.
- Exact differences relative to Strategy2:
  - Removes EMA and VWAP entry confirmation.
  - Restores separate entry and exit intervals.
  - Adds exit confirmation counters.

### Strategy4 / EMA + Confirmation

- File path: `strategy_development/local_implementation/strategies/strategy4.py`
- Class name: `Strategy4`
- Display name: `Strategy4 / EMA + Confirmation`
- Defaults: `lookback=14`, `vol_target=0.02`, `entry_interval=30`,
  `exit_interval=5`, `exit_confirmation_bars=4`, `ema_period=100`
- Fixed spec params: `{"lookback": 14, "vol_target": 0.02,
  "entry_interval": 30, "exit_interval": 5,
  "exit_confirmation_bars": 4, "ema_period": 100}`
- Required input data: same as Strategy0, with `Close` required for EMA.
- Indicators used:
  - Sigma bands.
  - Locally computed VWAP.
  - EMA from `minute_data["Close"].ewm(span=ema_period, adjust=False).mean()`.
  - Daily return volatility sizing.
- Entry rules:
  - Checked when flat and `minute % entry_interval == 0`.
  - Long if `current_price > upper_bound and current_price > ema_val`.
  - Short if `current_price < lower_bound and current_price < ema_val`.
  - Unlike Strategy2, local Strategy4 does not require price to be above/below
    VWAP for entry.
- Exit rules:
  - Same confirmed exit logic as Strategy3.
  - Long exit condition:
    `current_price < max(upper_bound, vwap_val)`.
  - Short exit condition:
    `current_price > min(lower_bound, vwap_val)`.
  - Liquidates after `exit_confirmation_bars` consecutive true checks.
  - Forced EOD exit at hour `15`, minute `>= 58`; counters reset.
- Position sizing: same dynamic leverage as Strategy0.
- Risk controls:
  - Volatility-scaled leverage.
  - EMA-filtered entries.
  - VWAP/band exit threshold.
  - Consecutive exit confirmation.
  - EOD flat rule.
- Session handling: same grouped-date logic as Strategy3.
- Transaction-cost handling: none in strategy class; handled by
  `BacktestEngine`.
- Directionality: long and short.
- EMA/VWAP/sigma/vol/confirmation:
  - Uses sigma bands, VWAP exits, EMA entry filter, volatility targeting, and
    confirmation counters.
- Exact differences relative to Strategy3:
  - Adds `ema_period`.
  - Computes an EMA on minute closes.
  - Requires EMA alignment for entry.
  - Keeps Strategy3's separate exit interval and confirmation counters.

## 3. Original vs local implementation

Reference files:

- `strategy_development/taken_strategies/strategy0.py`
- `strategy_development/taken_strategies/strategy1.py`
- `strategy_development/taken_strategies/strategy2.py`
- `strategy_development/taken_strategies/strategy3.py`
- `strategy_development/taken_strategies/strategy4.py`

Local files:

- `strategy_development/local_implementation/strategies/strategy0.py`
- `strategy_development/local_implementation/strategies/strategy1.py`
- `strategy_development/local_implementation/strategies/strategy2.py`
- `strategy_development/local_implementation/strategies/strategy3.py`
- `strategy_development/local_implementation/strategies/strategy4.py`

Preserved:

- The core breakout family is preserved: today's open, yesterday's close,
  minute-of-day sigma, upper and lower breakout bands, VWAP-based exits,
  end-of-day liquidation, and dynamic volatility-based sizing.
- The five variants are preserved at a high level:
  baseline, asymmetric intervals, EMA-filtered entries, confirmed exits, and
  EMA plus confirmed exits.
- Default core parameters are preserved: `lookback=14`, `vol_target=0.02`,
  `entry_interval=30`, `exit_interval=5`, `exit_confirmation_bars=4`,
  `ema_period=100`.
- Long and short trading are preserved.
- Leverage is capped at `2`.

Adapted:

- QuantConnect `QCAlgorithm` classes were adapted into plain Python strategy
  classes returning `Signal` objects.
- QuantConnect's live `VWAP` indicator was replaced by a cumulative intraday
  VWAP calculation from bar data.
- QuantConnect's `EMA` indicator was replaced by pandas `ewm`.
- `SetHoldings` and `Liquidate` were replaced by signal generation and local
  backtest execution.
- `Portfolio.Invested`, `IsLong`, and `IsShort` were replaced by an integer
  local `position` variable inside each strategy.
- Scheduled end-of-day state updates were replaced by grouped-day loops and
  last-bar session close updates.

Removed QuantConnect-specific assumptions:

- No `AlgorithmImports`.
- No `AddEquity`.
- No cloud or live data subscription.
- No QuantConnect scheduler.
- No brokerage fill model.
- No QuantConnect warm-up state.
- No QuantConnect portfolio object.

Added local Python/backtester assumptions:

- The strategy input frame must already exist locally and be normalized into
  `Open`, `High`, `Low`, `Close`, `Volume`.
- Fixed 15-minute experiments use
  `run_fixed_15m_experiments._to_market_frame` to convert lowercase processed
  OHLCV into strategy input format and convert timestamps to `US/Eastern`.
- Daily data for local runs is derived from intraday bars by
  `_build_daily_data`.
- Costs are deterministic and charged by notional turnover in
  `BacktestEngine`, not by the strategy classes.
- Equity is updated only at signal timestamps and final forced close, not on
  every bar.

15-minute adaptation:

- The original reference files subscribe to SPY at `Resolution.Minute`.
- The fixed local runner discovers processed assets with `frequency == "15min"`
  and applies the same strategy classes to 15-minute bars.
- Conditions like `minute % 30 == 0` still operate on the timestamp minute of
  each bar. On 15-minute data, this normally means entry checks can occur at
  timestamps such as `:00` and `:30`; 5-minute exit intervals do not create
  true 5-minute checks because there are only 15-minute bars.
- VWAP, EMA, sigma updates, exit confirmation counters, and EOD detection are
  therefore evaluated at 15-minute bar timestamps rather than every minute.
- This changes timing materially relative to the original minute strategy.

Whether the 5-minute SPY baseline is closer to the original:

- The original reference files are minute-resolution SPY strategies. A 5-minute
  SPY local baseline is closer than the 15-minute cross-asset adaptation in
  asset universe and timing granularity, but it is still not identical to the
  original because the local system uses offline bars, local VWAP/EMA
  calculations, signal-based backtesting, local transaction costs, and local
  session handling rather than QuantConnect's engine.

## 4. Backtest engine assumptions

The backtester is implemented in
`strategy_development/local_implementation/backtest/engine.py`.

How signals are passed:

- `BacktestEngine.run()` calls
  `strategy.generate_signals(daily_data, minute_data)`.
- Each `Signal` has `timestamp`, `direction`, `leverage`, and `reason`.
- For each signal, the engine reads the execution/reference price from
  `minute_data.loc[signal.timestamp, "Close"]`.

How positions are formed:

- The target exposure is `signal.direction * abs(signal.leverage)`.
- Direction `1` is long, `-1` is short, `0` is flat.
- `_position_delta(current_exposure, target_exposure)` separates closing
  exposure from opening exposure so changes in sign are treated as closing one
  side and opening the other.
- New entries set `entry_price`, `entry_time`, `entry_equity_base`, and
  `entry_notional`.
- `entry_notional = entry_equity_base * abs(current_exposure)`.

How equity curve is calculated:

- Gross and net equity both start at `initial_capital`, default `100000`.
- Trade PnL is realized when a position is closed:
  `direction * ((exit_price - entry_price) / entry_price) * entry_notional`.
- Gross equity adds gross trade PnL and never subtracts transaction cost.
- Net equity adds gross trade PnL and subtracts transaction cost.
- Equity rows are appended at signal timestamps and final forced engine close,
  not at every input bar.

How transaction costs are charged:

- Cost settings come from
  `strategy_development/local_implementation/costs.py`.
- Defaults are per-side basis points:
  equities `1.0`, commodities `1.5`, crypto `4.0`, default `2.0`.
- `cost_rate = cost_bps / 10000`.
- Costs are charged on notional turnover whenever exposure changes.
- Open turnover is `max(net_equity, 0.0) * open_exposure`.
- Close turnover is `max(net_equity, 0.0) * close_exposure`.
- Net equity is reduced by `turnover * cost_rate`.

How turnover is calculated:

- The engine accumulates dollar turnover in `total_turnover`.
- Each trade stores combined entry and exit turnover.
- Optimization metrics convert total turnover into a ratio through
  `optimization.metrics._turnover_ratio`, defined as
  `(total_turnover / bar_count) / initial_capital`.

Gross vs net:

- Gross metrics exclude transaction costs.
- Net metrics include transaction costs.
- The main `equity_curve` property returns the net equity curve.
- `BacktestResult.summary()` exposes both gross and net return and Sharpe
  fields, while `total_return_pct` and `sharpe_ratio` map to net values.

How trades are logged:

- A `Trade` object is appended whenever an existing exposure is closed.
- Trade fields include entry/exit time, direction, entry/exit price, leverage,
  gross PnL, net PnL, transaction cost, turnover, cumulative transaction cost,
  and gross/net return percentages.
- If a position remains open after all signals, the engine closes it at the
  final timestamp and final close price in `minute_data`.

Drawdowns and returns:

- `BacktestResult.summary()` computes returns from pct changes of the gross and
  net equity curves.
- Annualization in the engine is inferred by `_annualization_factor()` from the
  median spacing of equity-curve timestamps.
- Max drawdown is computed by `_max_drawdown_pct()` as
  `(equity / cumulative_peak - 1) * 100`.
- Optimization metrics use a fixed 15-minute annualization constant,
  `PERIODS_PER_YEAR_15M = 252 * 26`.

## 5. Optimization-relevant parameters

Parameter spaces are defined in
`strategy_development/local_implementation/optimization/param_spaces.py`.
Strategy-to-optimizer assignment is defined in
`strategy_development/local_implementation/optimization/common.py` by
`default_strategy_configs()`.

The optimizer assignment in code is:

- Strategy0: NES
- Strategy1: NES
- Strategy2: NES
- Strategy3: CMA-ES
- Strategy4: CMA-ES

The search objective is net Sharpe after transaction costs:

- Candidate search uses `reward = metrics.net_sharpe if valid else -1e6`.
- Search rows record both gross and net Sharpe, but `train_sharpe` is net
  Sharpe.
- Validation selection uses `_select_by_validation()`, which picks the highest
  validation `net_sharpe`, breaking ties with `net_total_return`.
- Backtests inside optimization call
  `run_backtest_for_params_with_costs()`, so transaction costs are included in
  the objective.
- Optimization loading intentionally uses train and validation only via
  `load_optimization_splits()`; it maps `train` and `validation` to local split
  partitions and excludes test.

Tunable parameters and bounds:

| Strategy | Optimizer | Tunable parameters |
|---|---:|---|
| Strategy0 | NES | `lookback` int 5 to 30 default 14; `vol_target` 0.005 to 0.05 default 0.02; `entry_interval` int 10 to 60 default 30 |
| Strategy1 | NES | Strategy0 params plus `exit_interval` int 1 to 30 default 5 |
| Strategy2 | NES | Strategy0 params plus `ema_period` int 20 to 200 default 100 |
| Strategy3 | CMA-ES | Strategy1 params plus `exit_confirmation_bars` int 1 to 10 default 4 |
| Strategy4 | CMA-ES | Strategy3 params plus `ema_period` int 20 to 200 default 100 |

## 6. Presentation explanation

### Presentation explanation

30-second explanation:

These five strategies are variations of the same intraday momentum breakout
idea. They compare the current intraday price against bands around today's open
and yesterday's close, where the band width is learned from historical
minute-of-day moves. If price breaks above the upper band they go long; if it
breaks below the lower band they go short. Position size is scaled to a daily
volatility target, and exits use VWAP, the band level, and an end-of-day flat
rule.

1-minute comparison:

Strategy0 is the baseline: 30-minute breakout checks, VWAP/band exits, and
volatility-scaled long or short exposure. Strategy1 keeps the same entries but
checks exits more often, so it can react faster after a trade is open. Strategy2
adds a trend filter: a breakout must also agree with VWAP and a 100-period EMA
before entry. Strategy3 removes the EMA filter but requires the exit condition
to persist for several checks before closing, reducing one-bar whipsaws.
Strategy4 combines EMA-filtered entries with confirmed exits, making it the
most constrained version in the local set. The trade-off across the sequence is
between responsiveness, noise filtering, and missed or delayed trades.

| Strategy | Core idea | Entry filter | Exit logic | Added complexity | Expected trade-off |
|---|---|---|---|---|---|
| Strategy0 / Baseline | Sigma-band intraday breakout | Price beyond upper/lower band | VWAP/band exit on 30-minute checks plus EOD exit | Low | Simple and responsive, but more whipsaw risk |
| Strategy1 / Asymmetric Intervals | Baseline with faster exits | Same as Strategy0 | VWAP/band exit checked every 5 minutes plus EOD exit | Low to medium | Faster risk reduction, potentially more exits |
| Strategy2 / EMA Filter | Breakout with trend confirmation | Band breakout plus VWAP and EMA alignment | Strategy0-style VWAP/band exit | Medium | Fewer false entries, but may miss valid breakouts |
| Strategy3 / Exit Confirmation | Breakout with delayed confirmed exits | Same as Strategy1 | VWAP/band exit must persist for 4 checks | Medium | Fewer whipsaw exits, but losses can be held longer |
| Strategy4 / EMA + Confirmation | EMA-filtered breakout with confirmed exits | Band breakout plus EMA alignment | Strategy3 confirmed VWAP/band exit | High | Most filtered, potentially lower turnover but slower reaction |

## 7. Professor Q&A

### What exactly did you reproduce?

The local implementation reproduces the five reference intraday momentum
strategy variants as offline Python signal generators and a local backtest
pipeline. The core logic reproduced is sigma-band intraday breakout, VWAP/band
exits, volatility-scaled sizing, long/short direction, and end-of-day
liquidation.

### How are the five strategies different?

Strategy0 is the baseline. Strategy1 adds separate faster exit checks.
Strategy2 adds EMA and VWAP entry confirmation. Strategy3 adds consecutive exit
confirmation. Strategy4 combines EMA entry filtering with exit confirmation.

### Did you preserve the original QuantConnect logic?

The main trading ideas and default parameters are preserved, but the execution
environment is not. QuantConnect scheduling, indicators, portfolio state,
`SetHoldings`, `Liquidate`, data subscription, and warm-up mechanics are
replaced by local pandas calculations, signal objects, and `BacktestEngine`.

### Why is 15-minute data an adaptation?

The reference files use minute-resolution SPY data. The fixed local experiments
run on processed 15-minute data across multiple asset classes. A condition like
`minute % 5 == 0` cannot create 5-minute decisions on 15-minute bars; the
strategy can only evaluate on bars that exist. That changes entry, exit, VWAP,
EMA, sigma, confirmation, and EOD timing.

### Where are transaction costs handled?

Transaction costs are centralized in
`strategy_development/local_implementation/costs.py` and applied in
`strategy_development/local_implementation/backtest/engine.py`. The strategy
classes themselves do not deduct costs.

### Are the strategies long-only or long/short?

All five are long/short. A breakout above the upper band emits a long signal;
a breakout below the lower band emits a short signal.

### What data do they need?

They need daily close data for volatility sizing and intraday OHLCV data for
signals. The local strategy methods expect daily `Close` and intraday `Open`,
`High`, `Low`, `Close`, `Volume` columns.

### Why optimize parameters?

The optimizer tunes parameters such as lookback, volatility target, check
intervals, EMA period, and exit confirmation bars to improve cost-aware net
Sharpe on training data, then selects candidates by validation net Sharpe.

### How do you avoid look-ahead bias?

The optimization pipeline avoids using the test split during fitting:
`load_optimization_splits()` loads only train and validation. Parameter search
uses train metrics, and final selection uses validation metrics. However, inside
the current local strategy classes, volatility sizing uses
`daily_returns[-lookback:]` from the full `daily_data` frame passed to the run
rather than a rolling window up to the current bar. That is a code-observed
look-ahead issue for the leverage calculation and should be treated as a
limitation of the current implementation.
