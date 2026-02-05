"""Trade reporting and statistics for paper trading.

This module provides classes for generating comprehensive trade
reports and statistics from paper trading sessions.
"""

import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeStatistics:
    """Comprehensive trading statistics.

    Attributes:
        total_trades: Total number of completed trades
        winning_trades: Number of profitable trades
        losing_trades: Number of unprofitable trades
        win_rate: Percentage of winning trades
        total_profit: Sum of all profits (absolute)
        total_loss: Sum of all losses (absolute)
        net_profit: Total profit minus losses
        avg_profit: Average profit per trade
        avg_loss: Average loss per losing trade
        profit_factor: Ratio of total profit to total loss
        largest_win: Largest single winning trade
        largest_loss: Largest single losing trade
        avg_trade_duration: Average duration of trades in seconds
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Sharpe ratio of returns
        total_return: Total return percentage
        total_leveraged_return: Total return with leverage
    """
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
    total_loss: float = 0.0
    net_profit: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_duration: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_return: float = 0.0
    total_leveraged_return: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary.

        Returns:
            Dictionary with all statistics
        """
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "net_profit": self.net_profit,
            "avg_profit": self.avg_profit,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "avg_trade_duration": self.avg_trade_duration,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "total_return": self.total_return,
            "total_leveraged_return": self.total_leveraged_return,
        }


class Statistics:
    """Calculator for trading statistics."""

    @staticmethod
    def calculate_from_records(records: List, leverage: int = 1) -> TradeStatistics:
        """Calculate statistics from trade records.

        Args:
            records: List of TradeRecord objects
            leverage: Leverage used in trading

        Returns:
            TradeStatistics object with calculated metrics
        """
        if not records:
            return TradeStatistics()

        # Extract profits
        profits = [r.profit for r in records]
        leveraged_profits = [r.leveraged_profit for r in records]
        durations = [
            (r.exit_time - r.position.entry_time).total_seconds()
            for r in records
        ]

        # Basic counts
        total_trades = len(records)
        winning_trades = sum(1 for p in profits if p > 0)
        losing_trades = sum(1 for p in profits if p < 0)

        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Profit/loss totals
        total_profit = sum(p for p in profits if p > 0)
        total_loss = abs(sum(p for p in profits if p < 0))
        net_profit = sum(profits)

        # Average profit/loss
        winning_profits = [p for p in profits if p > 0]
        losing_profits = [p for p in profits if p < 0]
        avg_profit = (sum(winning_profits) / len(winning_profits)) if winning_profits else 0
        avg_loss = (sum(losing_profits) / len(losing_profits)) if losing_profits else 0

        # Profit factor
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (
            float('inf') if total_profit > 0 else 0
        )

        # Largest win/loss
        largest_win = max(profits) if profits else 0
        largest_loss = min(profits) if profits else 0

        # Average duration
        avg_trade_duration = (sum(durations) / len(durations)) if durations else 0

        # Calculate drawdown
        max_drawdown = Statistics._calculate_max_drawdown(
            [r.percentual_profit for r in records]
        )

        # Sharpe ratio (simplified)
        sharpe_ratio = Statistics._calculate_sharpe_ratio(leveraged_profits)

        # Total return
        total_return = (net_profit / records[0].position.entry_price * 100) if records else 0
        total_leveraged_return = sum(leveraged_profits)

        return TradeStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=net_profit,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration=avg_trade_duration,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_return=total_return,
            total_leveraged_return=total_leveraged_return,
        )

    @staticmethod
    def _calculate_max_drawdown(returns: List[float]) -> float:
        """Calculate maximum drawdown from returns.

        Args:
            returns: List of percentage returns

        Returns:
            Maximum drawdown percentage
        """
        if not returns:
            return 0.0

        cumulative = 0
        peak = 0
        max_dd = 0

        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    @staticmethod
    def _calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio from returns.

        Args:
            returns: List of percentage returns
            risk_free_rate: Annual risk-free rate (default 0)

        Returns:
            Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        avg_return = sum(returns) / len(returns)

        # Calculate standard deviation
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        return (avg_return - risk_free_rate) / std_dev


@dataclass
class TradeReport:
    """Complete trade report.

    Attributes:
        symbol: Trading symbol
        timeframe: Timeframe used
        start_time: Backtest/paper trading start time
        end_time: Backtest/paper trading end time
        statistics: Trading statistics
        trade_records: List of individual trade records
    """
    symbol: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    statistics: TradeStatistics
    trade_records: List = field(default_factory=list)

    def print_summary(self) -> None:
        """Print a formatted summary of the report."""
        print("\n" + "=" * 60)
        print(f"TRADE REPORT: {self.symbol} ({self.timeframe})")
        print("=" * 60)
        print(f"Period: {self.start_time} to {self.end_time}")
        print("\n--- Trade Statistics ---")
        print(f"Total Trades: {self.statistics.total_trades}")
        print(f"Winning Trades: {self.statistics.winning_trades}")
        print(f"Losing Trades: {self.statistics.losing_trades}")
        print(f"Win Rate: {self.statistics.win_rate:.2f}%")
        print("\n--- Profit/Loss ---")
        print(f"Net Profit: {self.statistics.net_profit:.2f}")
        print(f"Total Profit: {self.statistics.total_profit:.2f}")
        print(f"Total Loss: {self.statistics.total_loss:.2f}")
        print(f"Profit Factor: {self.statistics.profit_factor:.2f}")
        print(f"Average Profit: {self.statistics.avg_profit:.2f}")
        print(f"Average Loss: {self.statistics.avg_loss:.2f}")
        print("\n--- Risk Metrics ---")
        print(f"Largest Win: {self.statistics.largest_win:.2f}")
        print(f"Largest Loss: {self.statistics.largest_loss:.2f}")
        print(f"Max Drawdown: {self.statistics.max_drawdown:.2f}%")
        print(f"Sharpe Ratio: {self.statistics.sharpe_ratio:.2f}")
        print("\n--- Returns ---")
        print(f"Total Return: {self.statistics.total_return:.2f}%")
        print(f"Total Leveraged Return: {self.statistics.total_leveraged_return:.2f}%")
        print(f"Avg Trade Duration: {self.statistics.avg_trade_duration/60:.2f} minutes")
        print("=" * 60 + "\n")

    def to_dataframe(self) -> pd.DataFrame:
        """Convert trade records to a DataFrame.

        Returns:
            DataFrame with trade details
        """
        if not self.trade_records:
            return pd.DataFrame()

        data = []
        for r in self.trade_records:
            data.append({
                "entry_time": r.position.entry_time,
                "exit_time": r.exit_time,
                "symbol": r.position.symbol,
                "side": r.side,
                "entry_price": r.position.entry_price,
                "exit_price": r.exit_price,
                "qty": r.position.qty,
                "leverage": r.position.leverage,
                "exit_reason": r.exit_reason,
                "profit": r.profit,
                "percentual_profit": r.percentual_profit,
                "leveraged_profit": r.leveraged_profit,
                "duration_seconds": (r.exit_time - r.position.entry_time).total_seconds(),
            })

        return pd.DataFrame(data)

    def save_to_csv(self, filepath: str) -> None:
        """Save trade records to CSV file.

        Args:
            filepath: Path to save CSV file
        """
        df = self.to_dataframe()
        if not df.empty:
            df.to_csv(filepath, index=False)
            logger.info(f"Trade report saved to {filepath}")

    def save_summary_to_txt(self, filepath: str) -> None:
        """Save summary report to text file.

        Args:
            filepath: Path to save text file
        """
        with open(filepath, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write(f"TRADE REPORT: {self.symbol} ({self.timeframe})\n")
            f.write("=" * 60 + "\n")
            f.write(f"Period: {self.start_time} to {self.end_time}\n\n")

            f.write("--- Trade Statistics ---\n")
            f.write(f"Total Trades: {self.statistics.total_trades}\n")
            f.write(f"Winning Trades: {self.statistics.winning_trades}\n")
            f.write(f"Losing Trades: {self.statistics.losing_trades}\n")
            f.write(f"Win Rate: {self.statistics.win_rate:.2f}%\n\n")

            f.write("--- Profit/Loss ---\n")
            f.write(f"Net Profit: {self.statistics.net_profit:.2f}\n")
            f.write(f"Total Profit: {self.statistics.total_profit:.2f}\n")
            f.write(f"Total Loss: {self.statistics.total_loss:.2f}\n")
            f.write(f"Profit Factor: {self.statistics.profit_factor:.2f}\n")
            f.write(f"Average Profit: {self.statistics.avg_profit:.2f}\n")
            f.write(f"Average Loss: {self.statistics.avg_loss:.2f}\n\n")

            f.write("--- Risk Metrics ---\n")
            f.write(f"Largest Win: {self.statistics.largest_win:.2f}\n")
            f.write(f"Largest Loss: {self.statistics.largest_loss:.2f}\n")
            f.write(f"Max Drawdown: {self.statistics.max_drawdown:.2f}%\n")
            f.write(f"Sharpe Ratio: {self.statistics.sharpe_ratio:.2f}\n\n")

            f.write("--- Returns ---\n")
            f.write(f"Total Return: {self.statistics.total_return:.2f}%\n")
            f.write(f"Total Leveraged Return: {self.statistics.total_leveraged_return:.2f}%\n")
            f.write(f"Avg Trade Duration: {self.statistics.avg_trade_duration/60:.2f} minutes\n")
            f.write("=" * 60 + "\n")

        logger.info(f"Summary report saved to {filepath}")
