"""Market data provider using yfinance with local CSV fallback.

Downloads and caches OHLCV data for backtesting intraday momentum strategies.
Supports multiple intervals and automatically falls back to bundled CSV files
included in the repository for reproducibility.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data_cache")
BUNDLED_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

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

    Falls back to bundled CSV files in the ``data/`` directory when
    live downloads are unavailable (e.g. inside Docker without internet).

    Parameters
    ----------
    ticker : str
        Ticker symbol, e.g. ``"SPY"``.
    cache_dir : Path | str
        Directory for download caches. Created automatically if missing.
    data_dir : Path | str | None
        Directory containing bundled CSV files. Defaults to ``data/``
        in the project root.

    Examples
    --------
    >>> provider = DataProvider("SPY")
    >>> df = provider.get_data("2026-04-01", "2026-05-01", interval="5m")
    """

    def __init__(
        self,
        ticker: str = "SPY",
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        data_dir: Path | str | None = None,
    ) -> None:
        self.ticker = ticker
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = Path(data_dir) if data_dir else BUNDLED_DATA_DIR

    def _load_bundled(self, filename: str) -> pd.DataFrame | None:
        """Try to load a bundled CSV file from the data directory.

        Parameters
        ----------
        filename : str
            Name of the CSV file (e.g. ``"spy_5m.csv"``).

        Returns
        -------
        pd.DataFrame | None
            Loaded data, or ``None`` if file not found.
        """
        path = self.data_dir / filename
        if not path.exists():
            return None
        logger.info("Loading bundled data from %s", path)
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index.name = "Datetime"
        # Convert to US/Eastern if timezone-aware (UTC from yfinance)
        if df.index.tz is not None:
            df.index = df.index.tz_convert("US/Eastern")
        elif any(c in filename for c in ["1m", "2m", "5m", "15m", "30m"]):
            # Intraday data from yfinance is UTC
            try:
                df.index = df.index.tz_localize("UTC").tz_convert("US/Eastern")
            except TypeError:
                pass
        return df

    def get_data(
        self,
        start: str,
        end: str,
        *,
        interval: str = "5m",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch intraday OHLCV data.

        First tries bundled CSV files, then cached downloads, then
        fetches fresh data from yfinance (chunked to stay within limits).
        Defaults to 5-minute bars for good balance of resolution
        and data availability.

        Parameters
        ----------
        start : str
            Start date in ``YYYY-MM-DD`` format.
        end : str
            End date in ``YYYY-MM-DD`` format.
        interval : str
            Bar interval: ``"1m"``, ``"2m"``, ``"5m"``, ``"15m"``, etc.
            Default is ``"5m"`` (60-day history, good resolution).
        use_cache : bool
            If ``True``, try to load from local cache first.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns ``Open, High, Low, Close, Volume``
            indexed by ``DatetimeIndex``.
        """
        # 1. Try bundled data
        bundled_map = {"5m": "spy_5m.csv", "1m": "spy_1m.csv", "2m": "spy_2m.csv"}
        bundled_file = bundled_map.get(interval)
        if bundled_file:
            df = self._load_bundled(bundled_file)
            if df is not None:
                mask = (df.index >= start) & (df.index <= end)
                subset = df.loc[mask]
                if not subset.empty:
                    logger.info("Using bundled data: %d rows", len(subset))
                    return subset

        # 2. Try cache
        cache = self.cache_dir / f"{self.ticker}_{interval}.parquet"
        if use_cache and cache.exists():
            logger.info("Loading cached data from %s", cache)
            df = pd.read_parquet(cache)
            mask = (df.index >= start) & (df.index <= end)
            subset = df.loc[mask]
            if not subset.empty:
                return subset

        # 3. Download fresh
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

        try:
            df.to_parquet(cache)
        except Exception:
            logger.warning("Could not cache data to parquet")

        return df

    def get_daily_data(self, start: str, end: str) -> pd.DataFrame:
        """Fetch daily OHLCV data for volatility calculations.

        Tries bundled CSV first, then downloads from yfinance.

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
        # Try bundled
        df = self._load_bundled("spy_daily.csv")
        if df is not None:
            mask = (df.index >= start) & (df.index <= end)
            subset = df.loc[mask]
            if not subset.empty:
                logger.info("Using bundled daily data: %d rows", len(subset))
                return subset

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
