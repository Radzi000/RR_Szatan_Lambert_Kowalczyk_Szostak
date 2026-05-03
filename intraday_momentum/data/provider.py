"""Market data provider using yfinance.

Downloads and caches minute-resolution OHLCV data for backtesting
intraday momentum strategies.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data_cache")


class DataProvider:
    """Download and cache minute-bar market data via yfinance.

    Parameters
    ----------
    ticker : str
        Ticker symbol, e.g. ``"SPY"``.
    cache_dir : Path | str
        Directory for CSV caches. Created automatically if missing.

    Examples
    --------
    >>> provider = DataProvider("SPY")
    >>> df = provider.get_data("2023-01-01", "2023-06-01")
    """

    def __init__(self, ticker: str = "SPY", cache_dir: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.ticker = ticker
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _cache_path(self) -> Path:
        return self.cache_dir / f"{self.ticker}_1m.parquet"

    def get_data(
        self,
        start: str,
        end: str,
        *,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch minute-bar OHLCV data.

        Parameters
        ----------
        start : str
            Start date in ``YYYY-MM-DD`` format.
        end : str
            End date in ``YYYY-MM-DD`` format.
        use_cache : bool
            If ``True``, try to load from local parquet cache first.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns ``Open, High, Low, Close, Volume``
            indexed by ``DatetimeIndex``.
        """
        if use_cache and self._cache_path.exists():
            logger.info("Loading cached data from %s", self._cache_path)
            df = pd.read_parquet(self._cache_path)
            mask = (df.index >= start) & (df.index <= end)
            subset = df.loc[mask]
            if not subset.empty:
                return subset

        logger.info("Downloading %s minute data %s -> %s", self.ticker, start, end)
        df = yf.download(
            self.ticker,
            start=start,
            end=end,
            interval="1m",
            progress=False,
        )
        if df.empty:
            msg = f"No data returned for {self.ticker} ({start} to {end})"
            raise ValueError(msg)

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index.name = "Datetime"
        df.to_parquet(self._cache_path)
        return df

    def get_daily_data(self, start: str, end: str) -> pd.DataFrame:
        """Fetch daily OHLCV data for volatility calculations.

        Parameters
        ----------
        start : str
            Start date in ``YYYY-MM-DD`` format.
        end : str
            End date in ``YYYY-MM-DD`` format.

        Returns
        -------
        pd.DataFrame
            Daily OHLCV data.
        """
        logger.info("Downloading %s daily data %s -> %s", self.ticker, start, end)
        df = yf.download(
            self.ticker,
            start=start,
            end=end,
            interval="1d",
            progress=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index.name = "Date"
        return df
