import os
import numpy as np
import pandas as pd

# 1. PARAMETER CONFIG (Authoritative fixed parameters mapped from QuantConnect originals)
STRATEGY_CONFIG = {
    "strategy0": {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "exit_interval": 30, "use_ema": False, "conf_bars": 0},
    "strategy1": {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "exit_interval": 5,  "use_ema": False, "conf_bars": 0},
    "strategy2": {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "exit_interval": 30, "use_ema": True,  "conf_bars": 0, "ema_period": 100},
    "strategy3": {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "exit_interval": 5,  "use_ema": False, "conf_bars": 4},
    "strategy4": {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "exit_interval": 5,  "use_ema": True,  "conf_bars": 4, "ema_period": 100}
}

# 2. BASE STRATEGY CLASS
class BaseStrategy:
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("Each strategy must implement generate_signals method.")

# 3. CORE MATHEMATICAL ENGINE FOR VOLATILITY BREAKOUT SIGNALS
def compute_intraday_momentum_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Faithfully reproduces the QuantConnect execution loop in vector/matrix format
    for high-fidelity Reproducible Research.
    """
    df = df.copy()
    lookback = config["lookback"]
    vol_target = config["vol_target"]
    
    # Ensure time calculations are derived from datetime index
    df['time_str'] = df.index.strftime('%H:%M')
    df['date'] = df.index.date
    
    # Calculate Daily Volatility Deque equivalents
    daily_close = df['close'].groupby(df['date']).last()
    daily_returns = daily_close.pct_change()
    daily_vol = daily_returns.rolling(window=lookback).std()
    
    # Map daily volatility back to intraday dataframe
    df['daily_vol'] = df['date'].map(daily_vol)
    
    # Intraday minute moves calculation: current_price / todays_open - 1
    df['todays_open'] = df['open'].groupby(df['date']).transform('first')
    df['yesterdays_close'] = df['date'].map(daily_close.shift(1))
    df['minute_move'] = (df['close'] / df['todays_open'] - 1).abs()
    
    # Compute rolling minute-of-day mean move (sigma) over last N days without look-ahead bias
    pivot_moves = df.pivot_table(index='date', columns='time_str', values='minute_move')
    rolling_sigma = pivot_moves.shift(1).rolling(window=lookback).mean()
    df_sigma = rolling_sigma.stack().reset_index(name='sigma')
    
    df = df.merge(df_sigma, on=['date', 'time_str'], how='left').set_index(df.index)
    df['sigma'] = df['sigma'].fillna(0)
    
    # Calculate Boundaries
    df['upper_bound'] = np.maximum(df['todays_open'], df['yesterdays_close']) * (1 + df['sigma'])
    df['lower_bound'] = np.minimum(df['todays_open'], df['yesterdays_close']) * (1 - df['sigma'])
    
    # Compute VWAP indicator natively
    cum_vol = df['volume'].groupby(df['date']).cumsum()
    cum_pv = (df['close'] * df['volume']).groupby(df['date']).cumsum()
    df['vwap'] = cum_pv / (cum_vol + 1e-9)
    
    # Optional EMA Filter
    if config.get("use_ema", False):
        df['ema'] = df['close'].ewm(span=config["ema_period"], adjust=False).mean()
    else:
        df['ema'] = df['close']
        
    # Execution simulator preserving cross-period confirmation states
    signals = np.zeros(len(df), dtype=int)
    invested = 0  
    long_exit_counter = 0
    short_exit_counter = 0
    
    prices = df['close'].values
    uppers = df['upper_bound'].values
    lowers = df['lower_bound'].values
    vwaps = df['vwap'].values
    emas = df['ema'].values
    minutes = df.index.minute
    hours = df.index.hour
    daily_vols = df['daily_vol'].values
    
    entry_int = config["entry_interval"]
    exit_int = config["exit_interval"]
    conf_bars = config["conf_bars"]
    use_ema = config.get("use_ema", False)
    
    for i in range(len(df)):
        # Market Close Liquidation at 15:58
        if hours[i] == 15 and minutes[i] >= 58:
            invested = 0
            long_exit_counter = 0
            short_exit_counter = 0
            signals[i] = 0
            continue
            
        # Initialization Guard
        if uppers[i] == 0 or lowers[i] == 0 or np.isnan(daily_vols[i]) or daily_vols[i] == 0:
            signals[i] = 0
            continue
            
        current_price = prices[i]
        
        # --- EXIT LOGIC (Checked every exit_interval minutes) ---
        if invested != 0 and (minutes[i] % exit_int == 0):
            if invested == 1:
                exit_level = max(uppers[i], vwaps[i])
                if current_price < exit_level:
                    long_exit_counter += 1
                else:
                    long_exit_counter = 0
                    
                if long_exit_counter >= conf_bars:
                    invested = 0
                    long_exit_counter = 0
                    
            elif invested == -1:
                exit_level = min(lowers[i], vwaps[i])
                if current_price > exit_level:
                    short_exit_counter += 1
                else:
                    short_exit_counter = 0
                    
                if short_exit_counter >= conf_bars:
                    invested = 0
                    short_exit_counter = 0

        # --- ENTRY LOGIC (Checked every entry_interval minutes) ---
        if invested == 0 and (minutes[i] % entry_int == 0):
            if use_ema:
                if current_price > uppers[i] and current_price > vwaps[i] and current_price > emas[i]:
                    invested = 1
                    long_exit_counter = 0
                elif current_price < lowers[i] and current_price < vwaps[i] and current_price < emas[i]:
                    invested = -1
                    short_exit_counter = 0
            else:
                if current_price > uppers[i]:
                    invested = 1
                    long_exit_counter = 0
                elif current_price < lowers[i]:
                    invested = -1
                    short_exit_counter = 0
                    
        signals[i] = invested

    df['signal'] = signals
    return df

# 4. EXPLICIT STRATEGY IMPLEMENTATIONS (Faithful to your original project design)
class FixedBaselineStrategy(BaseStrategy):
    """Benchmark: Simple Buy and Hold Strategy"""
    def __init__(self):
        super().__init__("Fixed_Baseline_BuyHold", {})
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 1
        return df

class Strategy0(BaseStrategy):
    """Accurate Intraday Momentum Baseline"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return compute_intraday_momentum_signals(df, self.config)

class Strategy1(BaseStrategy):
    """Intraday Momentum with Asymmetric Entry/Exit Intervals"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return compute_intraday_momentum_signals(df, self.config)

class Strategy2(BaseStrategy):
    """Intraday Momentum with EMA Trend Filter"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return compute_intraday_momentum_signals(df, self.config)

class Strategy3(BaseStrategy):
    """Intraday Momentum with Exit Confirmation Logic"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return compute_intraday_momentum_signals(df, self.config)

class Strategy4(BaseStrategy):
    """Intraday Momentum Combined (EMA Filter + Exit Confirmation)"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return compute_intraday_momentum_signals(df, self.config)

# 5. REPRODUCIBLE BACKTEST ENGINE
class BacktestEngine:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.df = self._load_data()
        
    def _load_data(self) -> pd.DataFrame:
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"File not found: {self.data_path}")
        df = pd.read_csv(self.data_path)
        df.columns = df.columns.str.lower()
        
        time_col = df.columns[0]
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.set_index(time_col).sort_index()
        return df

    def run(self, strategy: BaseStrategy) -> pd.DataFrame:
        df_signals = strategy.generate_signals(self.df)
        df_signals['market_returns'] = np.log(df_signals['close'] / df_signals['close'].shift(1))
        df_signals['strategy_returns'] = df_signals['market_returns'] * df_signals['signal'].shift(1)
        df_signals['cum_market_returns'] = df_signals['market_returns'].cumsum().apply(np.exp)
        df_signals['cum_strategy_returns'] = df_signals['strategy_returns'].cumsum().apply(np.exp)
        return df_signals

# 6. DETERMINISTIC REPRODUCTION EXECUTION
if __name__ == "__main__":
    file_to_test = "data/5min/spy_5m.csv"
    if not os.path.exists(file_to_test):
        file_to_test = "data/15min/equities/SPY.csv"
        
    if os.path.exists(file_to_test):
        print(f"Running authoritative replication for: {file_to_test}")
        engine = BacktestEngine(file_to_test)
        
        strategies = [
            FixedBaselineStrategy(),
            Strategy0("Strategy0_Baseline", STRATEGY_CONFIG["strategy0"]),
            Strategy1("Strategy1_Asymmetric", STRATEGY_CONFIG["strategy1"]),
            Strategy2("Strategy2_EMA_Filter", STRATEGY_CONFIG["strategy2"]),
            Strategy3("Strategy3_Confirmation", STRATEGY_CONFIG["strategy3"]),
            Strategy4("Strategy4_Combined", STRATEGY_CONFIG["strategy4"])
        ]
        
        for strat in strategies:
            try:
                results = engine.run(strat)
                final_return = results['cum_strategy_returns'].iloc[-1] if not results.empty else 1.0
                print(f"Strategy: {strat.name:<30} | Final Return: {final_return:.4f}")
            except Exception as e:
                print(f"Error executing {strat.name}: {e}")
    else:
        print("ERROR: Target data files not found.")
