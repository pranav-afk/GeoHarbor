"""Data pipeline orchestrator — wires all fetchers into a daily schedule."""
from datetime import date

from loguru import logger


class DataPipeline:
    @staticmethod
    def _select_tickers_for_debates(run_date: str, limit: int) -> list[str]:
        """Pick tickers to analyze after pipeline run.

        Preference order:
        1) Today's ML-ranked tickers (signal_labels.predicted_return)
        2) Fallback to NIFTY-50 universe for speed/coverage
        """
        if limit <= 0:
            return []

        # Try ML ranks for the day
        try:
            from sqlalchemy import text
            from india_quant.data.db import get_session

            with get_session() as s:
                rows = s.execute(
                    text(
                        """
                        SELECT ticker
                        FROM signal_labels
                        WHERE date = :d
                          AND horizon = '1d'
                          AND predicted_return IS NOT NULL
                        ORDER BY signal_rank ASC NULLS LAST
                        LIMIT :n
                        """
                    ),
                    {"d": run_date, "n": int(limit)},
                ).fetchall()
            tickers = [r[0] for r in rows if r and r[0]]
            if tickers:
                return tickers
        except Exception as e:
            logger.warning(f"[Pipeline] Debate ticker selection (ML) failed: {e}")

        # Fallback: NIFTY-50
        try:
            from india_quant.data.fetchers.yfinance_fetcher import YFinanceFetcher

            return list(YFinanceFetcher.NIFTY_ALPHA_50[: int(limit)])
        except Exception:
            return []

    @staticmethod
    def run_debates_after_pipeline(run_date: str, limit: int = 10):
        """Run debates + trade proposals so dashboard has verdict/conviction."""
        tickers = DataPipeline._select_tickers_for_debates(run_date, limit)
        if not tickers:
            logger.info("[Pipeline] No tickers selected for debate run.")
            return

        logger.info(f"[Pipeline] Running debates for {len(tickers)} tickers (date={run_date})")
        try:
            from india_quant.agents.judge import run_debate
            from india_quant.agents.trader import TraderAgent
        except Exception as e:
            logger.error(f"[Pipeline] Debate imports failed: {e}")
            return

        for t in tickers:
            try:
                debate = run_debate(t, run_date=run_date)
                TraderAgent().propose_trade(debate)
            except Exception as e:
                logger.error(f"[Pipeline] Debate failed for {t}: {e}")

    @staticmethod
    def run_pre_market(run_date: str = None):
        """
        08:00 IST: Fetch previous day's final prices, options snapshot, overnight news.
        run_date: 'YYYY-MM-DD' string (defaults to today)
        """
        run_date = run_date or date.today().isoformat()
        logger.info(f"[Pipeline] Pre-market run for {run_date}")

        # 1. Fetch EOD prices via yfinance
        try:
            from india_quant.data.fetchers.yfinance_fetcher import YFinanceFetcher
            fetcher = YFinanceFetcher()
            rows = fetcher.update_all()
            logger.info(f"[Pipeline] yfinance: {rows} rows updated")
        except Exception as e:
            logger.error(f"[Pipeline] yfinance failed: {e}")

        # 2. Fetch NSE option chain snapshot
        try:
            from india_quant.data.fetchers.nse_options_fetcher import NSEOptionsFetcher
            of = NSEOptionsFetcher()
            rows = of.fetch_and_store(["NIFTY", "BANKNIFTY"])
            logger.info(f"[Pipeline] Options: {rows} rows updated")
        except Exception as e:
            logger.error(f"[Pipeline] Options fetch failed: {e}")

        # 3. Fetch overnight news + score sentiment
        try:
            from india_quant.data.fetchers.news_fetcher import NewsFetcher
            from india_quant.data.fetchers.yfinance_fetcher import YFinanceFetcher
            nf = NewsFetcher()
            nifty_50 = YFinanceFetcher.NIFTY_50[:10]  # top 10 for speed
            rows = nf.fetch_and_store(nifty_50)
            logger.info(f"[Pipeline] News: {rows} articles stored")
        except Exception as e:
            logger.error(f"[Pipeline] News fetch failed: {e}")

        logger.info(f"[Pipeline] Pre-market run complete for {run_date}")
        # Alpha 50 screener — runs after price data is loaded
        try:
            from india_quant.signals.alpha50_screener import run_screener
            plans = run_screener(capital_inr=100_000, risk_per_trade_pct=0.01, top_n=8)
            logger.info(f"[Pipeline] Alpha50 screener: {len(plans)} stocks selected")
        except Exception as e:
            logger.error(f"[Pipeline] Alpha50 screener failed: {e}")

    @staticmethod
    def run_intraday():
        """
        Every 5 min 09:15-15:30: Angel SmartAPI live prices.
        Every 30 min: Refresh options chain.
        Every 60 min: Latest news.
        """
        logger.info("[Pipeline] Intraday update running...")

        try:
            from india_quant.data.fetchers.shoonya_fetcher import ShoonyaFetcher
            af = ShoonyaFetcher()
            # Tokens resolved automatically via searchscrip cache on first call
            logger.info("[Pipeline] Shoonya live prices: configure symbol tokens first")
        except Exception as e:
            logger.error(f"[Pipeline] Shoonya live fetch failed: {e}")

    @staticmethod
    def run_post_market(run_date: str = None, debates_limit: int = 10):
        """
        16:00 IST: Final EOD prices.
        16:30 IST: Compute factor scores.
        17:00 IST: Compute signal labels.
        17:30 IST: Run signal predictions.
        18:00 IST: Trigger report generation.
        """
        run_date = run_date or date.today().isoformat()
        logger.info(f"[Pipeline] Post-market run for {run_date}")

        try:
            from india_quant.data.fetchers.yfinance_fetcher import YFinanceFetcher
            fetcher = YFinanceFetcher()
            rows = fetcher.update_all()
            logger.info(f"[Pipeline] EOD prices: {rows} rows")
        except Exception as e:
            logger.error(f"[Pipeline] EOD fetch failed: {e}")

        try:
            from india_quant.signals.factors import FactorEngine
            fe = FactorEngine()
            fe.compute_all(run_date)
            logger.info("[Pipeline] Factor scores computed.")
        except Exception as e:
            logger.error(f"[Pipeline] Factor compute failed: {e}")

        try:
            from india_quant.signals.ml_models import ReturnPredictor
            rp = ReturnPredictor()
            predictions = rp.predict_today()
            logger.info(f"[Pipeline] ML predictions: {len(predictions)} tickers")
        except Exception as e:
            logger.error(f"[Pipeline] ML prediction failed: {e}")

        # Automatically generate debates so dashboard shows verdict/conviction
        if debates_limit and debates_limit > 0:
            try:
                DataPipeline.run_debates_after_pipeline(run_date, limit=int(debates_limit))
            except Exception as e:
                logger.error(f"[Pipeline] Auto-debate run failed: {e}")

        logger.info(f"[Pipeline] Post-market run complete for {run_date}")

    @staticmethod
    def run_weekly_maintenance():
        """Sunday 22:00: Retrain ML, data quality checks."""
        logger.info("[Pipeline] Weekly maintenance running...")

        try:
            from india_quant.signals.ml_models import ReturnPredictor
            rp = ReturnPredictor()
            rp.retrain_weekly()
            logger.info("[Pipeline] ML models retrained.")
        except Exception as e:
            logger.error(f"[Pipeline] Weekly retrain failed: {e}")

        try:
            from india_quant.data.quality_monitor import run_daily_quality_checks
            alerts = run_daily_quality_checks()
            if alerts:
                for a in alerts:
                    logger.warning(f"[Quality] {a}")
            else:
                logger.info("[Pipeline] Data quality: all checks passed.")
        except Exception as e:
            logger.error(f"[Pipeline] Quality check failed: {e}")
