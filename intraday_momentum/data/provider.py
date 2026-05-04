"""Market data provider using yfinance.

Downloads and caches OHLCV data for backtesting intraday momentum strategies.
Supports multiple intervals (1m, 2m, 5m, daily) with automatic chunking
for minute-level data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data_cache")

# yfinance constraints per interval
_INTERVAL_MAX_DAYS = {
    "1m": 7,
    "2m": 60,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "1h": 730,
}


class DataProvider:
    """Download and cache market data via yfinance.

    Parameters
    ----------
    ticker : str
        Ticker symbol, e.g. ``"SPY"``.
    cache_dir : Path | str
        Directory for parquet caches. Created automatically if missing.

    Examples
    --------
    >>> provider = DataProvider("SPY")
    >>> df = provider.get_data("2026-04-20", "2026-05-01")
    """

    def __init__(self, ticker: str = "SPY", cache_dir: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.ticker = ticker
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, interval: str) -> Path:
        return self.cache_dir / f"{self.ticker}_{interval}.parquet"

    def get_data(
        self,
        start: str,
        end: str,
        *,
        interval: str = "2m",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch intraday OHLCV data.

        Automatically chunks requests to stay within yfinance limits.
        Defaults to 2-minute bars, which offer a good balance of
        resolution and data availability (up to 60 days).

        Parameters
        ----------
        start : str
            Start date in ``YYYY-MM-DD`` format.
        end : str
            End date in ``YYYY-MM-DD`` format.
        interval : str
            Bar interval: ``"1m"``, ``"2m"``, ``"5m"``, ``"15m"``, etc.
            Default is ``"2m"`` (60-day history, sufficient resolution).
        use_cache : bool
            If ``True``, try to load from local parquet cache first.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns ``Open, High, Low, Close, Volume``
            indexed by ``DatetimeIndex``.
        """
        cache = self._cache_path(interval)
        if use_cache and cache.exists():
            logger.info("Loading cached data from %s", cache)
            df = pd.read_parquet(cache)
            mask = (df.index >= start) & (df.index <= end)
            subset = df.loc[mask]
            if not subset.empty:
                return subset

        logger.info("Downloading %s %s data %s -> %s", self.ticker, interval, start, end)

        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        max_days = _INTERVAL_MAX_DAYS.get(interval, 60)
        chunk_size = timedelta(days=max_days)

        all_chunks: list[pd.DataFrame] = []
        current = start_dt

        while current < end_dt:
            chunk_end = min(current + chunk_size, end_dt)
            logger.info(
                "  Chunk %s -> %s",
                current.strftime("%Y-%m-%d"),
                chunk_end.strftime("%Y-%m-%d"),
            )
            chunk = yf.download(
                self.ticker,
                start=current.strftime("%Y-%m-%d"),
                end=chunk_end.strftime("%Y-%m-%d"),
                interval=interval,
                progress=False,
            )
            if not chunk.empty:
                if isinstance(chunk.columns, pd.MultiIndex):
                    chunk.columns = chunk.columns.get_level_values(0)
                all_chunks.append(chunk)

            current = chunk_end

        if not all_chunks:
            msg = f"No data returned for {self.ticker} ({start} to {end}, interval={interval})"
            raise ValueError(msg)

        df = pd.concat(all_chunks)
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        df.index.name = "Datetime"

        # Convert to US/Eastern for strategy compatibility
        if df.index.tz is not None:
            df.index = df.index.tz_convert("US/Eastern")
        else:
            df.index = df.index.tz_localize("UTC").tz_convert("US/Eastern")

        df.to_parquet(cache)
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
