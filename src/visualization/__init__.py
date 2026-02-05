"""Visualization module for live trading data.

This module provides real-time plotting capabilities using Plotly and Dash.

Example:
    from src.visualization import create_plotter_for_trader

    # Attach a live plotter to any trader
    plotter = create_plotter_for_trader(trader, update_interval_ms=500, port=8050)

    # Access the live dashboard at http://127.0.0.1:8050
"""

from .live_plotter import LivePlotter, PlotConfig, create_plotter_for_trader

__all__ = ["LivePlotter", "PlotConfig", "create_plotter_for_trader"]
