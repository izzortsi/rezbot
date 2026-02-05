"""Live plotting with Plotly Dash.

This module provides real-time visualization of trading data using
Plotly Dash with automatic updates.
"""

from __future__ import annotations

import threading
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, TYPE_CHECKING
import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from dash import Dash, dcc, html, callback, Output, Input
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None  # type: ignore

from src.concurrency.threading import StoppableThread

logger = logging.getLogger(__name__)


@dataclass
class PlotConfig:
    """Configuration for live plotter.

    Attributes:
        update_interval_ms: Update interval in milliseconds
        port: Web server port
        host: Web server host
        show_candlesticks: Show OHLCV candlesticks
        show_bollinger: Show Bollinger Bands
        show_macd: Show MACD histogram
        show_trades: Show entry/exit markers
        show_pnl: Show cumulative P&L
        max_candles: Maximum candles to display
    """
    update_interval_ms: int = 1000
    port: int = 8050
    host: str = "127.0.0.1"
    show_candlesticks: bool = True
    show_bollinger: bool = True
    show_macd: bool = True
    show_trades: bool = True
    show_pnl: bool = True
    max_candles: int = 100


class LivePlotter(StoppableThread):
    """Real-time trading data plotter using Plotly Dash.

    This class runs a Dash web server in a separate thread to provide
    live visualization of trading data including:
    - OHLCV candlesticks with Bollinger Bands
    - MACD histogram
    - Entry/exit trade markers
    - Cumulative P&L chart

    Example:
        # Create plotter with trader reference
        config = PlotConfig(update_interval_ms=500, port=8050)
        plotter = LivePlotter(trader=trader, config=config)

        # Plotter auto-starts, access via http://127.0.0.1:8050

        # Stop when done
        plotter.stop()
    """

    def __init__(
        self,
        trader: Any,
        config: Optional[PlotConfig] = None,
        name: str = "live-plotter"
    ):
        """Initialize the live plotter.

        Args:
            trader: ThreadedATrader instance to visualize
            config: Plot configuration
            name: Thread name

        Raises:
            ImportError: If Plotly/Dash is not installed
        """
        if not PLOTLY_AVAILABLE:
            raise ImportError(
                "Plotly and Dash are required for live plotting. "
                "Install with: pip install plotly dash"
            )

        super().__init__(name=name, daemon=True)

        self.trader = trader
        self.config = config or PlotConfig()
        self._app: Optional[Dash] = None
        self._server_thread: Optional[threading.Thread] = None

        # Data cache for thread-safe access
        self._data_lock = threading.RLock()
        self._cached_data: Optional[pd.DataFrame] = None
        self._cached_trades: List[Any] = []
        self._cached_position: Optional[Any] = None
        self._cached_last_price: Optional[float] = None

        # Build Dash app
        self._build_app()

        # Auto-start
        self.start()
        logger.info(f"Live plotter started at http://{self.config.host}:{self.config.port}")

    def _build_app(self) -> None:
        """Build the Dash application."""
        self._app = Dash(__name__, update_title=None)

        # Determine subplot configuration
        rows = 1
        row_heights = [0.6]
        subplot_titles = ["Price"]

        if self.config.show_macd:
            rows += 1
            row_heights.append(0.25)
            subplot_titles.append("MACD")

        if self.config.show_pnl:
            rows += 1
            row_heights.append(0.15)
            subplot_titles.append("Cumulative P&L")

        # Normalize row heights
        total = sum(row_heights)
        row_heights = [h / total for h in row_heights]

        self._subplot_rows = rows
        self._row_heights = row_heights
        self._subplot_titles = subplot_titles

        # Layout
        self._app.layout = html.Div([
            html.H2(
                f"Live Trading: {self.trader.symbol}",
                style={"textAlign": "center", "color": "#2c3e50"}
            ),
            html.Div(id="status-bar", style={
                "textAlign": "center",
                "padding": "10px",
                "backgroundColor": "#ecf0f1",
                "marginBottom": "10px"
            }),
            dcc.Graph(
                id="live-chart",
                style={"height": "85vh"},
                config={"displayModeBar": True, "scrollZoom": True}
            ),
            dcc.Interval(
                id="interval-component",
                interval=self.config.update_interval_ms,
                n_intervals=0
            )
        ], style={"fontFamily": "Arial, sans-serif"})

        # Callbacks
        @self._app.callback(
            [Output("live-chart", "figure"), Output("status-bar", "children")],
            [Input("interval-component", "n_intervals")]
        )
        def update_chart(n):
            return self._create_figure(), self._create_status_bar()

    def _refresh_cache(self) -> None:
        """Refresh cached data from trader (thread-safe)."""
        with self._data_lock:
            try:
                # Copy data window
                self._cached_data = self.trader.data_window.copy()

                # Get live price from stream processor (most current tick)
                self._cached_last_price = self.trader.stream_processor.last_price

                # Get trade history
                self._cached_trades = self.trader.position_manager.get_trade_history()

                # Get current position
                self._cached_position = self.trader.position_manager.position

            except Exception as e:
                logger.error(f"Error refreshing cache: {e}")

    def _create_figure(self) -> go.Figure:
        """Create the Plotly figure with all subplots."""
        self._refresh_cache()

        with self._data_lock:
            data = self._cached_data
            trades = self._cached_trades
            position = self._cached_position
            last_price = self._cached_last_price

        if data is None or data.empty:
            return self._empty_figure()

        # Limit candles
        if len(data) > self.config.max_candles:
            data = data.tail(self.config.max_candles).reset_index(drop=True)

        # Update last candle with live price
        if last_price is not None and len(data) > 0:
            data = self._update_last_candle_with_live_price(data, last_price)

        # Create subplots
        fig = make_subplots(
            rows=self._subplot_rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=self._row_heights,
            subplot_titles=self._subplot_titles
        )

        current_row = 1

        # Row 1: Price with Bollinger Bands
        self._add_price_traces(fig, data, last_price, current_row)
        if self.config.show_bollinger:
            self._add_bollinger_bands(fig, data, current_row)
        if self.config.show_trades:
            self._add_trade_markers(fig, data, trades, position, current_row)

        # Row 2: MACD (if enabled)
        if self.config.show_macd:
            current_row += 1
            self._add_macd_histogram(fig, data, current_row)

        # Row 3: P&L (if enabled)
        if self.config.show_pnl:
            current_row += 1
            self._add_pnl_chart(fig, trades, current_row)

        # Update layout
        fig.update_layout(
            template="plotly_dark",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=80, b=30),
            xaxis_rangeslider_visible=False,
            hovermode="x unified"
        )

        # Update axes
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")

        return fig

    def _update_last_candle_with_live_price(
        self,
        data: pd.DataFrame,
        last_price: float
    ) -> pd.DataFrame:
        """Update the last candle with live price data.

        This ensures the last candlestick reflects real-time price movements:
        - Close is updated to the live price
        - High is updated if live price exceeds current high
        - Low is updated if live price is below current low

        Args:
            data: DataFrame with OHLCV data
            last_price: Current live price from stream processor

        Returns:
            Updated DataFrame with live price reflected in last candle
        """
        if len(data) == 0:
            return data

        # Work on a copy to avoid modifying cached data
        data = data.copy()

        # Use iloc[-1] to always get the actual last row regardless of index values
        close_col = data.columns.get_loc("close")
        data.iloc[-1, close_col] = last_price

        # Update high if live price exceeds it
        if "high" in data.columns:
            high_col = data.columns.get_loc("high")
            current_high = data.iloc[-1, high_col]
            if last_price > current_high:
                data.iloc[-1, high_col] = last_price

        # Update low if live price is below it
        if "low" in data.columns:
            low_col = data.columns.get_loc("low")
            current_low = data.iloc[-1, low_col]
            if last_price < current_low:
                data.iloc[-1, low_col] = last_price

        return data

    def _add_price_traces(
        self,
        fig: go.Figure,
        data: pd.DataFrame,
        last_price: Optional[float],
        row: int
    ) -> None:
        """Add price traces (candlesticks or line) with live price indicator."""
        if self.config.show_candlesticks and all(col in data.columns for col in ["open", "high", "low", "close"]):
            fig.add_trace(
                go.Candlestick(
                    x=data["date"],
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    name="Price",
                    increasing_line_color="#26a69a",
                    decreasing_line_color="#ef5350"
                ),
                row=row, col=1
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=data["date"],
                    y=data["close"],
                    mode="lines",
                    name="Close",
                    line=dict(color="#2196f3", width=2)
                ),
                row=row, col=1
            )

        # Add live price horizontal line
        if last_price is not None:
            fig.add_hline(
                y=last_price,
                line_dash="dot",
                line_color="#00bcd4",
                line_width=1,
                annotation_text=f"Live: {last_price:.2f}",
                annotation_position="right",
                annotation_font_color="#00bcd4",
                row=row, col=1
            )

    def _add_bollinger_bands(self, fig: go.Figure, data: pd.DataFrame, row: int) -> None:
        """Add Bollinger Bands overlay."""
        if "cs" not in data.columns or "ci" not in data.columns:
            return

        # Upper band
        fig.add_trace(
            go.Scatter(
                x=data["date"],
                y=data["cs"],
                mode="lines",
                name="Upper BB",
                line=dict(color="rgba(255, 193, 7, 0.6)", width=1, dash="dash")
            ),
            row=row, col=1
        )

        # Lower band
        fig.add_trace(
            go.Scatter(
                x=data["date"],
                y=data["ci"],
                mode="lines",
                name="Lower BB",
                line=dict(color="rgba(255, 193, 7, 0.6)", width=1, dash="dash"),
                fill="tonexty",
                fillcolor="rgba(255, 193, 7, 0.1)"
            ),
            row=row, col=1
        )

        # EMA
        if "close_ema" in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data["date"],
                    y=data["close_ema"],
                    mode="lines",
                    name="EMA",
                    line=dict(color="#9c27b0", width=1)
                ),
                row=row, col=1
            )

    def _add_trade_markers(
        self,
        fig: go.Figure,
        data: pd.DataFrame,
        trades: List[Any],
        position: Optional[Any],
        row: int
    ) -> None:
        """Add entry/exit trade markers."""
        # Entry markers from completed trades
        entry_dates = []
        entry_prices = []
        entry_colors = []
        entry_texts = []

        exit_dates = []
        exit_prices = []
        exit_colors = []
        exit_texts = []

        for trade in trades:
            # Entry
            entry_dates.append(trade.position.entry_time)
            entry_prices.append(trade.position.entry_price)
            is_long = trade.position.is_long
            entry_colors.append("#26a69a" if is_long else "#ef5350")
            entry_texts.append(f"{'LONG' if is_long else 'SHORT'} @ {trade.position.entry_price:.2f}")

            # Exit
            exit_dates.append(trade.exit_time)
            exit_prices.append(trade.exit_price)
            is_profitable = trade.is_profitable
            exit_colors.append("#26a69a" if is_profitable else "#ef5350")
            exit_texts.append(f"{trade.exit_reason} @ {trade.exit_price:.2f} ({trade.leveraged_profit:+.2f}%)")

        # Current open position
        if position:
            entry_dates.append(position.entry_time)
            entry_prices.append(position.entry_price)
            is_long = position.is_long
            entry_colors.append("#ffeb3b")  # Yellow for active position
            entry_texts.append(f"ACTIVE {'LONG' if is_long else 'SHORT'} @ {position.entry_price:.2f}")

        # Add entry markers
        if entry_dates:
            fig.add_trace(
                go.Scatter(
                    x=entry_dates,
                    y=entry_prices,
                    mode="markers",
                    name="Entries",
                    marker=dict(
                        symbol="triangle-up",
                        size=12,
                        color=entry_colors,
                        line=dict(color="white", width=1)
                    ),
                    text=entry_texts,
                    hovertemplate="%{text}<extra></extra>"
                ),
                row=row, col=1
            )

        # Add exit markers
        if exit_dates:
            fig.add_trace(
                go.Scatter(
                    x=exit_dates,
                    y=exit_prices,
                    mode="markers",
                    name="Exits",
                    marker=dict(
                        symbol="triangle-down",
                        size=12,
                        color=exit_colors,
                        line=dict(color="white", width=1)
                    ),
                    text=exit_texts,
                    hovertemplate="%{text}<extra></extra>"
                ),
                row=row, col=1
            )

    def _add_macd_histogram(self, fig: go.Figure, data: pd.DataFrame, row: int) -> None:
        """Add MACD histogram subplot."""
        if "histogram" not in data.columns:
            return

        colors = [
            "#26a69a" if v >= 0 else "#ef5350"
            for v in data["histogram"]
        ]

        fig.add_trace(
            go.Bar(
                x=data["date"],
                y=data["histogram"],
                name="MACD Histogram",
                marker_color=colors
            ),
            row=row, col=1
        )

        # Histogram EMA
        if "hist_ema" in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data["date"],
                    y=data["hist_ema"],
                    mode="lines",
                    name="Hist EMA",
                    line=dict(color="#ff9800", width=2)
                ),
                row=row, col=1
            )

        # Zero line
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=row, col=1)

    def _add_pnl_chart(self, fig: go.Figure, trades: List[Any], row: int) -> None:
        """Add cumulative P&L chart."""
        if not trades:
            return

        dates = [t.exit_time for t in trades]
        cumulative = []
        running_total = 0

        for trade in trades:
            running_total += trade.leveraged_profit
            cumulative.append(running_total)

        colors = ["#26a69a" if v >= 0 else "#ef5350" for v in cumulative]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=cumulative,
                mode="lines+markers",
                name="Cumulative P&L",
                line=dict(color="#2196f3", width=2),
                marker=dict(size=6, color=colors)
            ),
            row=row, col=1
        )

        # Zero line
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=row, col=1)

    def _empty_figure(self) -> go.Figure:
        """Return an empty figure with message."""
        fig = go.Figure()
        fig.add_annotation(
            text="Waiting for data...",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=24, color="gray")
        )
        fig.update_layout(template="plotly_dark")
        return fig

    def _create_status_bar(self) -> str:
        """Create status bar content."""
        with self._data_lock:
            data = self._cached_data
            position = self._cached_position
            trades = self._cached_trades
            last_price = self._cached_last_price

        parts = []

        # Live price (from stream processor - most current)
        if last_price is not None:
            parts.append(f"Live: {last_price:.4f}")
        elif data is not None and not data.empty:
            # Fallback to data window close
            parts.append(f"Price: {data['close'].iloc[-1]:.4f}")

        # Position status
        if position:
            side = "LONG" if position.is_long else "SHORT"
            parts.append(f"Position: {side} @ {position.entry_price:.2f}")
        else:
            parts.append("Position: FLAT")

        # Trade count and P&L
        if trades:
            total_pnl = sum(t.leveraged_profit for t in trades)
            wins = sum(1 for t in trades if t.is_profitable)
            parts.append(f"Trades: {len(trades)} (W: {wins})")
            parts.append(f"P&L: {total_pnl:+.2f}%")

        return " | ".join(parts)

    def _run_impl(self) -> None:
        """Run the Dash server."""
        # Run Flask server in current thread
        self._app.run(
            host=self.config.host,
            port=self.config.port,
            debug=False,
            use_reloader=False,
            threaded=True
        )

    def stop(self) -> None:
        """Stop the plotter gracefully."""
        super().stop()
        logger.info("Live plotter stopped")


def create_plotter_for_trader(
    trader: Any,
    update_interval_ms: int = 1000,
    port: int = 8050,
    **kwargs
) -> LivePlotter:
    """Convenience function to create a live plotter for a trader.

    Args:
        trader: ThreadedATrader instance
        update_interval_ms: Update interval in milliseconds
        port: Web server port
        **kwargs: Additional PlotConfig parameters

    Returns:
        LivePlotter instance (auto-started)

    Example:
        from src.visualization import create_plotter_for_trader

        plotter = create_plotter_for_trader(trader, update_interval_ms=500, port=8080)
        # Access at http://127.0.0.1:8080
    """
    config = PlotConfig(
        update_interval_ms=update_interval_ms,
        port=port,
        **kwargs
    )
    return LivePlotter(trader=trader, config=config)
