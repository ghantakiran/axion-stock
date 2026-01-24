"""Stock chart generation using Plotly for Streamlit display."""

import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


CHART_PERIODS = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "YTD": "ytd",
}

DARK_THEME = {
    "bg": "#0f0f1a",
    "paper": "#1a1a2e",
    "grid": "rgba(124, 58, 237, 0.08)",
    "text": "#a0aec0",
    "up": "#4ade80",
    "down": "#f87171",
    "line": "#7c3aed",
    "volume": "rgba(124, 58, 237, 0.3)",
    "ma20": "#60a5fa",
    "ma50": "#fbbf24",
}


def create_stock_chart(
    ticker: str,
    period: str = "6mo",
    chart_type: str = "candlestick",
    show_volume: bool = True,
    show_ma: bool = True,
) -> go.Figure:
    """Create a styled stock chart for a single ticker.

    Args:
        ticker: Stock symbol
        period: yfinance period string (1mo, 3mo, 6mo, 1y, ytd)
        chart_type: "candlestick" or "line"
        show_volume: Show volume subplot
        show_ma: Show 20 and 50 day moving averages

    Returns:
        Plotly Figure object
    """
    data = yf.download(ticker, period=period, auto_adjust=True, progress=False)

    if data.empty:
        return _empty_chart(ticker)

    # Flatten MultiIndex columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Compute moving averages
    data["MA20"] = data["Close"].rolling(20).mean()
    data["MA50"] = data["Close"].rolling(50).mean()

    # Create figure with volume subplot
    if show_volume:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.75, 0.25],
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    # Price chart
    if chart_type == "candlestick":
        fig.add_trace(
            go.Candlestick(
                x=data.index,
                open=data["Open"],
                high=data["High"],
                low=data["Low"],
                close=data["Close"],
                increasing_line_color=DARK_THEME["up"],
                decreasing_line_color=DARK_THEME["down"],
                increasing_fillcolor=DARK_THEME["up"],
                decreasing_fillcolor=DARK_THEME["down"],
                name=ticker,
            ),
            row=1, col=1,
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["Close"],
                mode="lines",
                line=dict(color=DARK_THEME["line"], width=2),
                name=ticker,
                fill="tozeroy",
                fillcolor="rgba(124, 58, 237, 0.05)",
            ),
            row=1, col=1,
        )

    # Moving averages
    if show_ma and len(data) > 20:
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["MA20"],
                mode="lines",
                line=dict(color=DARK_THEME["ma20"], width=1, dash="dot"),
                name="MA20",
                opacity=0.7,
            ),
            row=1, col=1,
        )
        if len(data) > 50:
            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["MA50"],
                    mode="lines",
                    line=dict(color=DARK_THEME["ma50"], width=1, dash="dot"),
                    name="MA50",
                    opacity=0.7,
                ),
                row=1, col=1,
            )

    # Volume bars
    if show_volume:
        colors = [
            DARK_THEME["up"] if c >= o else DARK_THEME["down"]
            for c, o in zip(data["Close"], data["Open"])
        ]
        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data["Volume"],
                marker_color=colors,
                opacity=0.4,
                name="Volume",
                showlegend=False,
            ),
            row=2, col=1,
        )

    # Price change annotation
    if len(data) >= 2:
        start_price = float(data["Close"].iloc[0])
        end_price = float(data["Close"].iloc[-1])
        change_pct = (end_price / start_price - 1) * 100
        change_color = DARK_THEME["up"] if change_pct >= 0 else DARK_THEME["down"]
        change_sign = "+" if change_pct >= 0 else ""
        title_text = f"{ticker}  ${end_price:.2f}  <span style='color:{change_color}'>{change_sign}{change_pct:.1f}%</span>"
    else:
        title_text = ticker

    # Layout styling
    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=16, color="#e2e8f0"),
            x=0.02,
        ),
        plot_bgcolor=DARK_THEME["bg"],
        paper_bgcolor=DARK_THEME["paper"],
        font=dict(color=DARK_THEME["text"], size=11),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        margin=dict(l=50, r=20, t=60, b=20),
        height=400,
        hovermode="x unified",
    )

    # Axis styling
    for ax in ["xaxis", "yaxis", "xaxis2", "yaxis2"]:
        if ax in fig.layout:
            fig.update_layout(**{
                ax: dict(
                    gridcolor=DARK_THEME["grid"],
                    zerolinecolor=DARK_THEME["grid"],
                    showgrid=True,
                )
            })

    fig.update_xaxes(showspikes=True, spikecolor="#7c3aed", spikethickness=1)
    fig.update_yaxes(showspikes=True, spikecolor="#7c3aed", spikethickness=1)

    return fig


def create_comparison_chart(tickers: list[str], period: str = "6mo") -> go.Figure:
    """Create normalized comparison chart for multiple tickers."""
    fig = go.Figure()

    colors = ["#7c3aed", "#60a5fa", "#4ade80", "#fbbf24", "#f87171"]

    for i, ticker in enumerate(tickers[:5]):
        data = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if data.empty:
            continue

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Normalize to percentage change from start
        normalized = (data["Close"] / data["Close"].iloc[0] - 1) * 100

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=normalized,
                mode="lines",
                name=ticker,
                line=dict(color=colors[i % len(colors)], width=2),
            )
        )

    fig.update_layout(
        title=dict(
            text="Relative Performance",
            font=dict(size=16, color="#e2e8f0"),
            x=0.02,
        ),
        plot_bgcolor=DARK_THEME["bg"],
        paper_bgcolor=DARK_THEME["paper"],
        font=dict(color=DARK_THEME["text"], size=11),
        yaxis_title="Return (%)",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=50, r=20, t=60, b=20),
        height=350,
        hovermode="x unified",
        xaxis=dict(gridcolor=DARK_THEME["grid"]),
        yaxis=dict(gridcolor=DARK_THEME["grid"], zerolinecolor="rgba(124,58,237,0.3)"),
    )

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=1)

    return fig


def create_factor_chart(scores: dict, ticker: str) -> go.Figure:
    """Create a radar/bar chart showing factor scores."""
    factors = ["Value", "Momentum", "Quality", "Growth"]
    values = [
        scores.get("value", 0.5),
        scores.get("momentum", 0.5),
        scores.get("quality", 0.5),
        scores.get("growth", 0.5),
    ]
    colors = ["#60a5fa", "#c084fc", "#4ade80", "#fbbf24"]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=factors,
            y=values,
            marker_color=colors,
            marker_line_color=colors,
            marker_line_width=1,
            opacity=0.8,
            text=[f"{v:.2f}" for v in values],
            textposition="outside",
            textfont=dict(color="#e2e8f0", size=12),
        )
    )

    # Add median line
    fig.add_hline(
        y=0.5, line_dash="dash",
        line_color="rgba(255,255,255,0.3)", line_width=1,
        annotation_text="Median",
        annotation_position="right",
        annotation_font_color="#64748b",
    )

    fig.update_layout(
        title=dict(
            text=f"{ticker} Factor Scores",
            font=dict(size=14, color="#e2e8f0"),
            x=0.02,
        ),
        plot_bgcolor=DARK_THEME["bg"],
        paper_bgcolor=DARK_THEME["paper"],
        font=dict(color=DARK_THEME["text"], size=11),
        yaxis=dict(range=[0, 1.1], gridcolor=DARK_THEME["grid"], title="Score"),
        xaxis=dict(gridcolor=DARK_THEME["grid"]),
        margin=dict(l=50, r=20, t=50, b=30),
        height=280,
        showlegend=False,
    )

    return fig


def _empty_chart(ticker: str) -> go.Figure:
    """Return empty chart with message."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"No data available for {ticker}",
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="#64748b"),
    )
    fig.update_layout(
        plot_bgcolor=DARK_THEME["bg"],
        paper_bgcolor=DARK_THEME["paper"],
        height=200,
    )
    return fig
