import os
import numpy as np
import pandas as pd

# Strategy parameters configuration for easy optimization access
STRATEGY_CONFIG = {
    "strategy0": {"short_window": 12, "long_window": 26},
    "strategy1": {"window": 14, "lower_bound": 30, "upper_bound": 70},
    "strategy2": {"window": 20, "num_std": 2},
    "strategy3": {"short_window": 12, "long_window": 26, "signal_window": 9},
    "strategy4": {"window": 14}
}

class BaseStrategy:
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("Each strategy must implement generate_signals method.")

class FixedBaselineStrategy(BaseStrategy):
    """Benchmark: Buy and Hold Strategy"""
    def __init__(self):
        super().__init__("Fixed_Baseline_BuyHold", {})
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 1
        return df

class Strategy0(BaseStrategy):
    """Moving Average Crossover"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        short_w = self.config["short_window"]
        long_w = self.config["long_window"]
        
        df['short_mavg'] = df['Close'].rolling(window=short_w, min_periods=1).mean()
        df['long_mavg'] = df['Close'].rolling(window=long_w, min_periods=1).mean()
        
        df['signal'] = 0
        df.loc[df['short_mavg'] > df['long_mavg'], 'signal'] = 1
        df.loc[df['short_mavg'] < df['long_mavg'], 'signal'] = -1
        return df

class Strategy1(BaseStrategy):
    """Relative Strength Index (RSI)"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        window = self.config["window"]
        lower = self.config["lower_bound"]
        upper = self.config["upper_bound"]
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / (loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['signal'] = 0
        df.loc[df['rsi'] < lower, 'signal'] = 1
        df.loc[df['rsi'] > upper, 'signal'] = -1
        return df

class Strategy2(BaseStrategy):
    """Bollinger Bands"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        window = self.config["window"]
        num_std = self.config["num_std"]
        
        df['rolling_mean'] = df['Close'].rolling(window=window).mean()
        df['rolling_std'] = df['Close'].rolling(window=window).std()
        df['bollinger_high'] = df['rolling_mean'] + (df['rolling_std'] * num_std)
        df['bollinger_low'] = df['rolling_mean'] - (df['rolling_std'] * num_std)
        
        df['signal'] = 0
        df.loc[df['Close'] < df['bollinger_low'], 'signal'] = 1
        df.loc[df['Close'] > df['bollinger_high'], 'signal'] = -1
        return df

class Strategy3(BaseStrategy):
    """MACD (Moving Average Convergence Divergence)"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        short_w = self.config["short_window"]
        long_w = self.config["long_window"]
        sig_w = self.config["signal_window"]
        
        df['exp1'] = df['Close'].ewm(span=short_w, adjust=False).mean()
        df['exp2'] = df['Close'].ewm(span=long_w, adjust=False).mean()
        df['macd'] = df['exp1'] - df['exp2']
        df['exp3'] = df['macd'].ewm(span=sig_w, adjust=False).mean()
        
        df['signal'] = 0
        df.loc[df['macd'] > df['exp3'], 'signal'] = 1
        df.loc[df['macd'] < df['exp3'], 'signal'] = -1
        return df

class Strategy4(BaseStrategy):
    """Momentum Strategy"""
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        window = self.config["window"]
        
        df['momentum'] = df['Close'].diff(window)
        
        df['signal'] = 0
        df.loc[df['momentum'] > 0, 'signal'] = 1
        df.loc[df['momentum'] < 0, 'signal'] = -1
        return df

class BacktestEngine:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.df = self._load_data()
        
    def _load_data(self) -> pd.DataFrame:
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"File not found: {self.data_path}")
        
        df = pd.read_csv(self.data_path)
        time_col = df.columns[0]
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.set_index(time_col).sort_index()
        return df

    def run(self, strategy: BaseStrategy) -> pd.DataFrame:
        df_signals = strategy.generate_signals(self.df)
        
        # Calculate log returns
        df_signals['market_returns'] = np.log(df_signals['Close'] / df_signals['Close'].shift(1))
        
        # Shift signal by 1 period to avoid look-ahead bias
        df_signals['strategy_returns'] = df_signals['market_returns'] * df_signals['signal'].shift(1)
        
        # Cumulative returns
        df_signals['cum_market_returns'] = df_signals['market_returns'].cumsum().apply(np.exp)
        df_signals['cum_strategy_returns'] = df_signals['strategy_returns'].cumsum().apply(np.exp)
        
        return df_signals

if __name__ == "__main__":
    file_to_test = "BTCUSDT.csv"
    
    if os.path.exists(file_to_test):
        print(f"Running backtest for: {file_to_test}")
        engine = BacktestEngine(file_to_test)
        
        strategies = [
            FixedBaselineStrategy(),
            Strategy0("MA_Crossover", STRATEGY_CONFIG["strategy0"]),
            Strategy1("RSI_Strategy", STRATEGY_CONFIG["strategy1"]),
            Strategy2("Bollinger_Bands", STRATEGY_CONFIG["strategy2"]),
            Strategy3("MACD_Strategy", STRATEGY_CONFIG["strategy3"]),
            Strategy4("Momentum_Strategy", STRATEGY_CONFIG["strategy4"])
        ]
        
        for strat in strategies:
            results = engine.run(strat)
            final_return = results['cum_strategy_returns'].iloc[-1] if not results.empty else 1.0
            print(f"Strategy: {strat.name:<25} | Final Return: {final_return:.4f}")
