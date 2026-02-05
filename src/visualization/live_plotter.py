"""Live plotting with Plotly Dash.

This module provides real-time visualization of trading data using
Plotly Dash with automatic updates. Supports single-symbol and
multi-symbol (2x2 grid) dashboards.
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


# ---------------------------------------------------------------------------
# Module-level helper functions (shared by LivePlotter & MultiTraderDashboard)
# ---------------------------------------------------------------------------

def _update_last_candle(data: pd.DataFrame, last_price: float) -> pd.DataFrame:
    """Update the last candle with live price data.

    Close is set to the live price. High/low are expanded if the live
    price exceeds the current range.

    Args:
        data: DataFrame with OHLCV data (must not be empty)
        last_price: Current live price

    Returns:
        Copy of DataFrame with live price reflected in last candle
    """
    data = data.copy()

    close_col = data.columns.get_loc("close")
    data.iloc[-1, close_col] = last_price

    if "high" in data.columns:
        high_col = data.columns.get_loc("high")
        if last_price > data.iloc[-1, high_col]:
            data.iloc[-1, high_col] = last_price

    if "low" in data.columns:
        low_col = data.columns.get_loc("low")
        if last_price < data.iloc[-1, low_col]:
            data.iloc[-1, low_col] = last_price

    return data


def _add_price_traces(
    fig: go.Figure,
    data: pd.DataFrame,
    last_price: Optional[float],
    row: int,
    config: PlotConfig,
) -> None:
    """Add price traces (candlesticks or line) with live price indicator."""
    if config.show_candlesticks and all(
        col in data.columns for col in ["open", "high", "low", "close"]
    ):
        fig.add_trace(
            go.Candlestick(
                x=data["date"],
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                name="Price",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            ),
            row=row, col=1,
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=data["date"],
                y=data["close"],
                mode="lines",
                name="Close",
                line=dict(color="#2196f3", width=2),
            ),
            row=row, col=1,
        )

    if last_price is not None:
        fig.add_hline(
            y=last_price,
            line_dash="dot",
            line_color="#00bcd4",
            line_width=1,
            annotation_text=f"Live: {last_price:.2f}",
            annotation_position="right",
            annotation_font_color="#00bcd4",
            row=row, col=1,
        )


def _add_bollinger_bands(fig: go.Figure, data: pd.DataFrame, row: int) -> None:
    """Add Bollinger Bands overlay."""
    if "cs" not in data.columns or "ci" not in data.columns:
        return

    fig.add_trace(
        go.Scatter(
            x=data["date"], y=data["cs"],
            mode="lines", name="Upper BB",
            line=dict(color="rgba(255, 193, 7, 0.6)", width=1, dash="dash"),
        ),
        row=row, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=data["date"], y=data["ci"],
            mode="lines", name="Lower BB",
            line=dict(color="rgba(255, 193, 7, 0.6)", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(255, 193, 7, 0.1)",
        ),
        row=row, col=1,
    )

    if "close_ema" in data.columns:
        fig.add_trace(
            go.Scatter(
                x=data["date"], y=data["close_ema"],
                mode="lines", name="EMA",
                line=dict(color="#9c27b0", width=1),
            ),
            row=row, col=1,
        )


def _add_trade_markers(
    fig: go.Figure,
    data: pd.DataFrame,
    trades: List[Any],
    position: Optional[Any],
    row: int,
) -> None:
    """Add entry/exit trade markers."""
    entry_dates, entry_prices, entry_colors, entry_texts = [], [], [], []
    exit_dates, exit_prices, exit_colors, exit_texts = [], [], [], []

    for trade in trades:
        entry_dates.append(trade.position.entry_time)
        entry_prices.append(trade.position.entry_price)
        is_long = trade.position.is_long
        entry_colors.append("#26a69a" if is_long else "#ef5350")
        entry_texts.append(f"{'LONG' if is_long else 'SHORT'} @ {trade.position.entry_price:.2f}")

        exit_dates.append(trade.exit_time)
        exit_prices.append(trade.exit_price)
        exit_colors.append("#26a69a" if trade.is_profitable else "#ef5350")
        exit_texts.append(
            f"{trade.exit_reason} @ {trade.exit_price:.2f} ({trade.leveraged_profit:+.2f}%)"
        )

    if position:
        entry_dates.append(position.entry_time)
        entry_prices.append(position.entry_price)
        is_long = position.is_long
        entry_colors.append("#ffeb3b")
        entry_texts.append(f"ACTIVE {'LONG' if is_long else 'SHORT'} @ {position.entry_price:.2f}")

    if entry_dates:
        fig.add_trace(
            go.Scatter(
                x=entry_dates, y=entry_prices,
                mode="markers", name="Entries",
                marker=dict(symbol="triangle-up", size=12, color=entry_colors,
                            line=dict(color="white", width=1)),
                text=entry_texts, hovertemplate="%{text}<extra></extra>",
            ),
            row=row, col=1,
        )

    if exit_dates:
        fig.add_trace(
            go.Scatter(
                x=exit_dates, y=exit_prices,
                mode="markers", name="Exits",
                marker=dict(symbol="triangle-down", size=12, color=exit_colors,
                            line=dict(color="white", width=1)),
                text=exit_texts, hovertemplate="%{text}<extra></extra>",
            ),
            row=row, col=1,
        )


def _add_macd_histogram(fig: go.Figure, data: pd.DataFrame, row: int) -> None:
    """Add MACD histogram subplot."""
    if "histogram" not in data.columns:
        return

    colors = ["#26a69a" if v >= 0 else "#ef5350" for v in data["histogram"]]

    fig.add_trace(
        go.Bar(x=data["date"], y=data["histogram"], name="MACD Histogram",
               marker_color=colors),
        row=row, col=1,
    )

    if "hist_ema" in data.columns:
        fig.add_trace(
            go.Scatter(x=data["date"], y=data["hist_ema"], mode="lines",
                       name="Hist EMA", line=dict(color="#ff9800", width=2)),
            row=row, col=1,
        )

    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5,
                  row=row, col=1)


def _add_pnl_chart(fig: go.Figure, trades: List[Any], row: int) -> None:
    """Add cumulative P&L chart."""
    if not trades:
        return

    dates = [t.exit_time for t in trades]
    cumulative = []
    running = 0.0
    for trade in trades:
        running += trade.leveraged_profit
        cumulative.append(running)

    colors = ["#26a69a" if v >= 0 else "#ef5350" for v in cumulative]

    fig.add_trace(
        go.Scatter(x=dates, y=cumulative, mode="lines+markers",
                   name="Cumulative P&L",
                   line=dict(color="#2196f3", width=2),
                   marker=dict(size=6, color=colors)),
        row=row, col=1,
    )

    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5,
                  row=row, col=1)


def _empty_figure(message: str = "Waiting for data...") -> go.Figure:
    """Return an empty figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=24, color="gray"),
    )
    fig.update_layout(template="plotly_dark")
    return fig


def build_symbol_figure(
    data: Optional[pd.DataFrame],
    trades: List[Any],
    position: Optional[Any],
    last_price: Optional[float],
    config: PlotConfig,
) -> go.Figure:
    """Build a complete Plotly figure for a single symbol.

    Returns a make_subplots figure with price+BB, MACD, and P&L rows.
    """
    if data is None or data.empty:
        return _empty_figure()

    if len(data) > config.max_candles:
        data = data.tail(config.max_candles).reset_index(drop=True)

    if last_price is not None and len(data) > 0:
        data = _update_last_candle(data, last_price)

    # Subplot configuration
    rows = 1
    row_heights = [0.6]
    titles: List[str] = ["Price"]

    if config.show_macd:
        rows += 1
        row_heights.append(0.25)
        titles.append("MACD")

    if config.show_pnl:
        rows += 1
        row_heights.append(0.15)
        titles.append("Cumulative P&L")

    total = sum(row_heights)
    row_heights = [h / total for h in row_heights]

    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=row_heights,
        subplot_titles=titles,
    )

    current_row = 1
    _add_price_traces(fig, data, last_price, current_row, config)
    if config.show_bollinger:
        _add_bollinger_bands(fig, data, current_row)
    if config.show_trades:
        _add_trade_markers(fig, data, trades, position, current_row)

    if config.show_macd:
        current_row += 1
        _add_macd_histogram(fig, data, current_row)

    if config.show_pnl:
        current_row += 1
        _add_pnl_chart(fig, trades, current_row)

    fig.update_layout(
        template="plotly_dark",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=80, b=30),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")

    return fig


def _build_status_text(
    data: Optional[pd.DataFrame],
    position: Optional[Any],
    trades: List[Any],
    last_price: Optional[float],
) -> str:
    """Build status bar text for a single symbol."""
    parts: List[str] = []

    if last_price is not None:
        parts.append(f"Live: {last_price:.4f}")
    elif data is not None and not data.empty:
        parts.append(f"Price: {data['close'].iloc[-1]:.4f}")

    if position:
        side = "LONG" if position.is_long else "SHORT"
        parts.append(f"Position: {side} @ {position.entry_price:.2f}")
    else:
        parts.append("Position: FLAT")

    if trades:
        total_pnl = sum(t.leveraged_profit for t in trades)
        wins = sum(1 for t in trades if t.is_profitable)
        parts.append(f"Trades: {len(trades)} (W: {wins})")
        parts.append(f"P&L: {total_pnl:+.2f}%")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# LivePlotter — single-symbol dashboard (original, refactored to use helpers)
# ---------------------------------------------------------------------------

class LivePlotter(StoppableThread):
    """Real-time trading data plotter using Plotly Dash.

    This class runs a Dash web server in a separate thread to provide
    live visualization of trading data including:
    - OHLCV candlesticks with Bollinger Bands
    - MACD histogram
    - Entry/exit trade markers
    - Cumulative P&L chart

    Example:
        config = PlotConfig(update_interval_ms=500, port=8050)
        plotter = LivePlotter(trader=trader, config=config)
        # Access via http://127.0.0.1:8050
        plotter.stop()
    """

    def __init__(
        self,
        trader: Any,
        config: Optional[PlotConfig] = None,
        name: str = "live-plotter",
    ):
        if not PLOTLY_AVAILABLE:
            raise ImportError(
                "Plotly and Dash are required for live plotting. "
                "Install with: pip install plotly dash"
            )

        super().__init__(name=name, daemon=True)

        self.trader = trader
        self.config = config or PlotConfig()
        self._app: Optional[Dash] = None

        self._data_lock = threading.RLock()
        self._cached_data: Optional[pd.DataFrame] = None
        self._cached_trades: List[Any] = []
        self._cached_position: Optional[Any] = None
        self._cached_last_price: Optional[float] = None

        self._build_app()
        self.start()
        logger.info(f"Live plotter started at http://{self.config.host}:{self.config.port}")

    def _build_app(self) -> None:
        """Build the Dash application."""
        self._app = Dash(__name__, update_title=None,
                         suppress_callback_exceptions=True)

        self._app.layout = html.Div([
            html.H2(
                f"Live Trading: {self.trader.symbol}",
                style={"textAlign": "center", "color": "#2c3e50"},
            ),
            html.Div(id="status-bar", style={
                "textAlign": "center", "padding": "10px",
                "backgroundColor": "#ecf0f1", "marginBottom": "10px",
            }),
            dcc.Graph(
                id="live-chart",
                style={"height": "85vh"},
                config={"displayModeBar": True, "scrollZoom": True},
            ),
            dcc.Interval(
                id="interval-component",
                interval=self.config.update_interval_ms,
                n_intervals=0,
            ),
        ], style={"fontFamily": "Arial, sans-serif"})

        @self._app.callback(
            [Output("live-chart", "figure"), Output("status-bar", "children")],
            [Input("interval-component", "n_intervals")],
        )
        def update_chart(n):
            return self._create_figure(), self._create_status_bar()

    def _refresh_cache(self) -> None:
        """Refresh cached data from trader (thread-safe)."""
        with self._data_lock:
            try:
                self._cached_data = self.trader.data_window.copy()
                self._cached_last_price = self.trader.stream_processor.last_price
                self._cached_trades = self.trader.position_manager.get_trade_history()
                self._cached_position = self.trader.position_manager.position
            except Exception as e:
                logger.error(f"Error refreshing cache: {e}")

    def _create_figure(self) -> go.Figure:
        """Create the Plotly figure with all subplots."""
        self._refresh_cache()
        with self._data_lock:
            return build_symbol_figure(
                self._cached_data,
                self._cached_trades,
                self._cached_position,
                self._cached_last_price,
                self.config,
            )

    def _create_status_bar(self) -> str:
        """Create status bar content."""
        with self._data_lock:
            return _build_status_text(
                self._cached_data,
                self._cached_position,
                self._cached_trades,
                self._cached_last_price,
            )

    def _run_impl(self) -> None:
        """Run the Dash server."""
        self._app.run(
            host=self.config.host,
            port=self.config.port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    def stop(self) -> None:
        """Stop the plotter gracefully."""
        super().stop()
        logger.info("Live plotter stopped")


# ---------------------------------------------------------------------------
# MultiTraderDashboard — multi-symbol 2x2 grid dashboard
# ---------------------------------------------------------------------------

class MultiTraderDashboard(StoppableThread):
    """Multi-symbol dashboard with a 2x2 CSS grid of independent charts.

    Each grid cell contains a full chart (candlestick + BB, MACD, P&L)
    for one symbol. Supports 1-4 symbols.

    Example:
        dashboard = MultiTraderDashboard(traders=[t1, t2, t3])
        # Access via http://127.0.0.1:8050
        dashboard.stop()
    """

    def __init__(
        self,
        traders: List[Any],
        config: Optional[PlotConfig] = None,
        name: str = "multi-dashboard",
    ):
        if not PLOTLY_AVAILABLE:
            raise ImportError(
                "Plotly and Dash are required for live plotting. "
                "Install with: pip install plotly dash"
            )

        super().__init__(name=name, daemon=True)

        self.traders = traders
        self.config = config or PlotConfig()
        self._app: Optional[Dash] = None

        self._data_lock = threading.RLock()
        self._caches: Dict[int, dict] = {
            i: {"data": None, "trades": [], "position": None, "last_price": None}
            for i in range(len(traders))
        }

        self._build_app()
        self.start()
        logger.info(
            f"Multi-symbol dashboard started at "
            f"http://{self.config.host}:{self.config.port} "
            f"({len(traders)} symbols)"
        )

    def _build_app(self) -> None:
        """Build the Dash application with CSS grid layout."""
        self._app = Dash(__name__, update_title=None,
                         suppress_callback_exceptions=True)
        n = len(self.traders)

        grid_children = []
        for i, trader in enumerate(self.traders):
            cell = html.Div([
                html.H3(
                    trader.symbol.upper(),
                    style={"textAlign": "center", "color": "#e0e0e0",
                           "margin": "5px 0"},
                ),
                html.Div(id=f"status-{i}", style={
                    "textAlign": "center", "padding": "5px",
                    "backgroundColor": "#2c3e50", "color": "#ecf0f1",
                    "fontSize": "12px", "marginBottom": "5px",
                    "borderRadius": "3px",
                }),
                dcc.Graph(
                    id=f"chart-{i}",
                    style={"height": "80vh" if n == 1 else "42vh"},
                    config={"displayModeBar": True, "scrollZoom": True},
                ),
            ], style={
                "border": "1px solid #34495e", "borderRadius": "4px",
                "padding": "5px", "backgroundColor": "#111111",
            })
            grid_children.append(cell)

        grid_cols = "1fr" if n == 1 else "1fr 1fr"

        self._app.layout = html.Div([
            html.H2(
                "Rezbot Multi-Symbol Dashboard",
                style={"textAlign": "center", "color": "#e0e0e0",
                       "margin": "10px 0"},
            ),
            html.Div(
                grid_children,
                style={
                    "display": "grid",
                    "gridTemplateColumns": grid_cols,
                    "gap": "10px",
                    "padding": "10px",
                },
            ),
            dcc.Interval(
                id="interval-component",
                interval=self.config.update_interval_ms,
                n_intervals=0,
            ),
        ], style={
            "fontFamily": "Arial, sans-serif",
            "backgroundColor": "#1a1a2e",
            "minHeight": "100vh",
        })

        # Single callback returning all figures + statuses
        outputs = []
        for i in range(n):
            outputs.append(Output(f"chart-{i}", "figure"))
            outputs.append(Output(f"status-{i}", "children"))

        @self._app.callback(outputs, [Input("interval-component", "n_intervals")])
        def update_all(n_intervals):
            results = []
            for i in range(len(self.traders)):
                self._refresh_cache(i)
                with self._data_lock:
                    cache = self._caches[i]
                fig = build_symbol_figure(
                    cache["data"], cache["trades"],
                    cache["position"], cache["last_price"],
                    self.config,
                )
                # Compact legend for grid cells
                fig.update_layout(showlegend=False)
                status = _build_status_text(
                    cache["data"], cache["position"],
                    cache["trades"], cache["last_price"],
                )
                results.append(fig)
                results.append(status)
            return results

    def _refresh_cache(self, idx: int) -> None:
        """Refresh cached data for a specific trader."""
        trader = self.traders[idx]
        with self._data_lock:
            try:
                self._caches[idx]["data"] = trader.data_window.copy()
                self._caches[idx]["last_price"] = trader.stream_processor.last_price
                self._caches[idx]["trades"] = trader.position_manager.get_trade_history()
                self._caches[idx]["position"] = trader.position_manager.position
            except Exception as e:
                logger.error(f"Error refreshing cache for {trader.symbol}: {e}")

    def _run_impl(self) -> None:
        """Run the Dash server."""
        self._app.run(
            host=self.config.host,
            port=self.config.port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    def stop(self) -> None:
        """Stop the dashboard gracefully."""
        super().stop()
        logger.info("Multi-symbol dashboard stopped")


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def create_plotter_for_trader(
    trader: Any,
    update_interval_ms: int = 1000,
    port: int = 8050,
    **kwargs,
) -> LivePlotter:
    """Convenience function to create a live plotter for a single trader."""
    config = PlotConfig(update_interval_ms=update_interval_ms, port=port, **kwargs)
    return LivePlotter(trader=trader, config=config)


def create_dashboard_for_traders(
    traders: List[Any],
    update_interval_ms: int = 1000,
    port: int = 8050,
    **kwargs,
) -> StoppableThread:
    """Create a live dashboard for one or more traders.

    For a single trader, returns a LivePlotter (existing behavior).
    For multiple traders, returns a MultiTraderDashboard with 2x2 grid.
    """
    config = PlotConfig(update_interval_ms=update_interval_ms, port=port, **kwargs)
    if len(traders) == 1:
        return LivePlotter(trader=traders[0], config=config)
    return MultiTraderDashboard(traders=traders, config=config)
