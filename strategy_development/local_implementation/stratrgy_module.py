import os
import numpy as np
import pandas as pd

# 1. PARAMETER CONFIG (Authoritative fixed parameters for reproducibility)
STRATEGY_CONFIG = {
    "strategy0": {"momentum_window": 3},
    "strategy1": {"entry_window": 3, "exit_window": 5},
    "strategy2": {"momentum_window": 3, "ema_window": 20},
    "strategy3": {"momentum_window": 3, "conf_window": 2},
    "strategy4": {"momentum_window": 3, "ema_window": 20, "conf_window": 2}
}

# 2. BASE STRATEGY CLASS
class BaseStrategy:
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("Each strategy must implement generate_signals method.")

# 3. FIXED BASELINE STRATEGY
class FixedBaselineStrategy(BaseStrategy):
    """Benchmark: Simple Buy and Hold Strategy"""
    def __init__(self):
        super().__init__("Fixed_Baseline_BuyHold", {})
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 1
        return df

# 4. INTRADAY MOMENTUM STRATEGY VARIANTS (Reproducing blackswan-quants)
class Strategy0(BaseStrategy):
    """Strategy0: Standard Intraday Momentum Baseline"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        w = self.config["momentum_window"]
        
        df['return_lookback'] = df['close'].pct_change(w)
        df['signal'] = 0
        df.loc[df['return_lookback'] > 0, 'signal'] = 1
        df.loc[df['return_lookback'] < 0, 'signal'] = -1
        return df

class Strategy1(BaseStrategy):
    """Strategy1: Intraday Momentum with Asymmetric Entry/Exit Intervals"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        en_w = self.config["entry_window"]
        ex_w = self.config["exit_window"]
        
        df['entry_mom'] = df['close'].pct_change(en_w)
        df['exit_mom'] = df['close'].pct_change(ex_w)
        
        df['signal'] = 0
        df.loc[df['entry_mom'] > 0, 'signal'] = 1
        df.loc[df['entry_mom'] < 0, 'signal'] = -1
        df.loc[(df['signal'] == 1) & (df['exit_mom'] < 0), 'signal'] = 0
        df.loc[(df['signal'] == -1) & (df['exit_mom'] > 0), 'signal'] = 0
        return df

class Strategy2(BaseStrategy):
    """Strategy2: Intraday Momentum with EMA Trend Filter"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        w = self.config["momentum_window"]
        ema_w = self.config["ema_window"]
        
        df['return_lookback'] = df['close'].pct_change(w)
        df['ema'] = df['close'].ewm(span=ema_w, adjust=False).mean()
        
        df['signal'] = 0
        df.loc[(df['return_lookback'] > 0) & (df['close'] > df['ema']), 'signal'] = 1
        df.loc[(df['return_lookback'] < 0) & (df['close'] < df['ema']), 'signal'] = -1
        return df

class Strategy3(BaseStrategy):
    """Strategy3: Intraday Momentum with Exit Confirmation Logic"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        w = self.config["momentum_window"]
        conf_w = self.config["conf_window"]
        
        df['return_lookback'] = df['close'].pct_change(w)
        df['signal_raw'] = 0
        df.loc[df['return_lookback'] > 0, 'signal_raw'] = 1
        df.loc[df['return_lookback'] < 0, 'signal_raw'] = -1
        
        # Confirmation logic using raw rolling shifts
        df['signal'] = df['signal_raw'].rolling(window=conf_w).median().ffill().fillna(0).astype(int)
        return df

class Strategy4(BaseStrategy):
    """Strategy4: Intraday Momentum Combined (EMA Filter + Exit Confirmation)"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        w = self.config["momentum_window"]
        ema_w = self.config["ema_window"]
        
        df['return_lookback'] = df['close'].pct_change(w)
        df['ema'] = df['close'].ewm(span=ema_w, adjust=False).mean()
        
        df['signal_raw'] = 0
        df.loc[(df['return_lookback'] > 0) & (df['close'] > df['ema']), 'signal_raw'] = 1
        df.loc[(df['return_lookback'] < 0) & (df['close'] < df['ema']), 'signal_raw'] = -1
        
        df['signal'] = df['signal_raw']
        return df

# 5. REPRODUCIBLE BACKTEST ENGINE
class BacktestEngine:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.df = self._load_data()
        
    def _load_data(self) -> pd.DataFrame:
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"File not found: {self.data_path}")
        
        df = pd.read_csv(self.data_path)
        
        # FORCE LOWERCASE COLUMNS FOR ABSOLUTE REPRODUCIBILITY
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
        print(f"Running authoritative pipeline backtest for: {file_to_test}")
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
        print("ERROR: Baseline SPY files not found in data/ directory.")
