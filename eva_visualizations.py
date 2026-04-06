"""
Pure visualization functions for EVA charts.

Each function accepts data parameters and returns a Plotly HTML string
(or None when the chart cannot be produced from the given data).
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


def create_ev_bar_chart(results: pd.DataFrame) -> str:
    """EV by Subzone bar chart."""
    fig = go.Figure(data=[
        go.Bar(
            x=results['Subzone ID'],
            y=results['EV'],
            marker=dict(
                color=results['EV'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="EV")
            ),
            text=results['EV'].round(2),
            textposition='outside'
        )
    ])

    fig.update_layout(
        title="Ecological Value by Subzone",
        xaxis_title="Subzone ID",
        yaxis_title="Ecological Value (EV)",
        height=500,
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(include_plotlyjs="cdn", div_id="ev_plot")


def create_feature_heatmap(df: pd.DataFrame) -> str:
    """Feature Distribution heatmap."""
    # Get feature columns (exclude Subzone ID)
    feature_cols = [col for col in df.columns if col != 'Subzone ID']

    # Create heatmap data
    heatmap_data = df[feature_cols].values

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=feature_cols,
        y=df['Subzone ID'],
        colorscale='Blues',
        hoverongaps=False,
        colorbar=dict(title="Presence")
    ))

    fig.update_layout(
        title="Feature Distribution Across Subzones",
        xaxis_title="Features",
        yaxis_title="Subzone ID",
        height=max(400, len(df) * 20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(include_plotlyjs="cdn", div_id="feature_plot")


def create_aq_breakdown_chart(results: pd.DataFrame) -> str | None:
    """AQ Breakdown by Subzone grouped bar + EV line.

    Returns None if no active AQ columns are present.
    """
    aq_columns = [col for col in results.columns if col.startswith('AQ')]
    if not aq_columns:
        return None

    # Filter to active AQs (those with at least one non-zero value)
    active_aqs = [col for col in aq_columns if results[col].abs().sum() > 0]
    if not active_aqs:
        return None

    fig = go.Figure()

    # Add bars for each active AQ
    colors = px.colors.qualitative.Plotly
    for i, aq in enumerate(active_aqs):
        fig.add_trace(go.Bar(
            name=aq,
            x=results['Subzone ID'],
            y=results[aq],
            marker_color=colors[i % len(colors)],
            hovertemplate=f'{aq}: %{{y:.2f}}<extra></extra>'
        ))

    # Add EV line overlay
    fig.add_trace(go.Scatter(
        name='EV',
        x=results['Subzone ID'],
        y=results['EV'],
        mode='lines+markers',
        line=dict(color='black', width=2, dash='dot'),
        marker=dict(size=6, color='black'),
        hovertemplate='EV: %{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title="AQ Score Breakdown by Subzone",
        xaxis_title="Subzone ID",
        yaxis_title="Score (0-5)",
        yaxis=dict(range=[0, 5.5]),
        barmode='group',
        height=550,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(include_plotlyjs="cdn", div_id="aq_breakdown_plot")


def create_aq_radar_chart(results: pd.DataFrame, selected_subzones: list) -> str | None:
    """AQ Radar Comparison across selected subzones.

    Returns None if no AQ columns are present or *selected_subzones* is empty.
    """
    if not selected_subzones:
        return None

    aq_columns = [col for col in results.columns if col.startswith('AQ')]
    if not aq_columns:
        return None

    fig = go.Figure()

    line_colors = px.colors.qualitative.Plotly
    fill_colors = [
        'rgba(99,110,250,0.15)', 'rgba(239,85,59,0.15)', 'rgba(0,204,150,0.15)',
        'rgba(171,99,250,0.15)', 'rgba(255,161,90,0.15)'
    ]

    for i, subzone in enumerate(selected_subzones):
        row = results[results['Subzone ID'] == subzone]
        if row.empty:
            continue
        values = row[aq_columns].values.flatten().tolist()
        values.append(values[0])  # Close the polygon
        categories = aq_columns + [aq_columns[0]]

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            fillcolor=fill_colors[i % len(fill_colors)],
            name=str(subzone),
            line=dict(color=line_colors[i % len(line_colors)], width=2),
            hovertemplate='%{theta}: %{r:.2f}<extra>' + str(subzone) + '</extra>'
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 5]),
            angularaxis=dict(direction="clockwise")
        ),
        title="AQ Profile Comparison by Subzone",
        height=600,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(include_plotlyjs="cdn", div_id="radar_plot")


def create_aq_heatmap(results: pd.DataFrame, color_scheme: str) -> str | None:
    """AQ Heatmap sorted by EV descending.

    Returns None if no AQ columns are present.
    """
    aq_columns = [col for col in results.columns if col.startswith('AQ')]
    if not aq_columns:
        return None

    display_cols = aq_columns + ['EV']
    sorted_results = results.sort_values('EV', ascending=True)

    z_data = sorted_results[display_cols].values
    x_labels = display_cols
    y_labels = sorted_results['Subzone ID'].tolist()

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=x_labels,
        y=y_labels,
        colorscale=color_scheme,
        zmin=0,
        zmax=5,
        text=np.round(z_data, 1),
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False,
        colorbar=dict(title="Score")
    ))

    fig.update_layout(
        title="AQ Scores × Subzones (sorted by EV)",
        xaxis_title="Assessment Questions",
        yaxis_title="Subzone ID",
        height=max(450, len(sorted_results) * 25),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(include_plotlyjs="cdn", div_id="aq_heatmap_plot")


def create_aq_histogram(results: pd.DataFrame) -> str | None:
    """AQ Scores histogram.

    Returns None if no AQ columns are present.
    """
    aq_columns = [col for col in results.columns if col.startswith('AQ')]
    # Filter to active AQs only (at least one non-zero, non-NaN value)
    aq_columns = [col for col in aq_columns if results[col].abs().sum() > 0]
    if not aq_columns:
        return None

    # Melt the dataframe to get all AQ scores in one column
    aq_data = results[aq_columns].values.flatten()

    fig = go.Figure(data=[
        go.Histogram(
            x=aq_data,
            nbinsx=30,
            marker=dict(
                color='rgba(255, 152, 0, 0.7)',
                line=dict(color='rgba(255, 152, 0, 1)', width=1)
            )
        )
    ])

    fig.update_layout(
        title="Distribution of Assessment Question Scores",
        xaxis_title="AQ Score",
        yaxis_title="Frequency",
        height=400,
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(include_plotlyjs="cdn", div_id="aq_plot")
