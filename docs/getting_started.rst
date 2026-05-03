Getting Started
===============

Installation
------------

Clone the repository and install dependencies::

    git clone https://github.com/Radzi000/RR_Szatan_Lambert_Kowalczyk_Szostak.git
    cd RR_Szatan_Lambert_Kowalczyk_Szostak
    make dev

Using Docker
------------

Build and run inside Docker::

    make docker-build
    docker compose run --rm app

Running a Backtest
------------------

.. code-block:: python

    from intraday_momentum.data.provider import DataProvider
    from intraday_momentum.strategies import Strategy0
    from intraday_momentum.backtest.engine import BacktestEngine

    # Download data
    provider = DataProvider("SPY")
    daily = provider.get_daily_data("2023-01-01", "2023-12-31")
    minute = provider.get_data("2023-11-01", "2023-12-31")

    # Run strategy
    strategy = Strategy0(lookback=14, vol_target=0.02)
    engine = BacktestEngine(initial_capital=100_000)
    result = engine.run(strategy, daily, minute)

    print(result.summary())

Running Tests
-------------

::

    make test

Building Documentation
----------------------

::

    make docs
