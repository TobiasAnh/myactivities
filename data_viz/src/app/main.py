import dash
import dash_bootstrap_components as dbc
import plotly.io as pio
import plotly.express as px
import pandas as pd
import logging
from dash import dcc, html, dash_table
from datetime import datetime
from app.utils import (
    columns_short,
    columns_shorter,
    col_rename_dict,
    activity_mapping,
    get_engine,
    fetch_data,
    convert_units,
    generate_folium_map,
    get_metric_card,
    update_date_axis,
    get_speedometer,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Get current year and aimed distance goal
current_year = datetime.now().year
start_date = pd.to_datetime(f"{current_year}-01-01")
end_date = pd.to_datetime(f"{current_year}-12-31")
days_in_year = (end_date - start_date).days + 1

# Define annual distance goal
# total_goal_distance = 8000  # NOTE Hardcoded
# daily_distance_goal = total_goal_distance / days_in_year  # km/day
# goal_dates = pd.date_range(start_date, end_date, freq="D")
# goal_distances = daily_distance_goal * (goal_dates - start_date).days

# try:
#     activities = pd.read_csv("src/app/activities.csv", index_col="activity_id")
# except:
#     activities = pd.read_csv(
#         "data_fetch/src/app/activities.csv", index_col="activity_id"
#     )


# Connect and fetch data from psql
engine = get_engine()
athlete = fetch_data(
    engine,
    "SELECT * FROM athlete",
    index_col="athlete_id",
)

activities = fetch_data(
    engine,
    "SELECT * FROM activities",
    "activity_id",
)

activities = activities.drop_duplicates()
activities["start_date"] = pd.to_datetime(activities["start_date"])
activities = activities.sort_values("start_date", ascending=False)

# Tidy up activities dataframe
activities_ready = convert_units(activities, rounding_digits=1)
activities_ready["name"] = activities_ready["name"].apply(
    lambda x: x[:40]
)  # Shorten names for display


# Get cumulative distance for each year
activities_ready = activities_ready.reset_index()
activities_ready["start_year"] = activities_ready["start_date"].dt.year
activities_ready["annual_cumulative_distance"] = (
    activities_ready.sort_values("start_date")
    .groupby("start_year")["distance"]
    .cumsum()
)
activities_ready = activities_ready.set_index("activity_id")
activities_ready = activities_ready.copy()
activities_ready["start_date_current_year"] = activities_ready["start_date"].apply(
    lambda x: x.replace(year=current_year)
)

activities_ready["CURRENT_YEAR"] = current_year


# Creating df of annual summaries
annual_cycling = activities[
    activities["sport_type"].isin(["Ride", "MountainBikeRide", "VirtualRide"])
]
annual_cycling = annual_cycling.groupby(
    activities["start_date"].dt.tz_convert(None).dt.to_period("Y")
).agg(
    n_activities=("resource_state", "size"),
    total_distance=("distance", "sum"),
    total_moving_time=("moving_time", "sum"),
    total_elevation_gain=("total_elevation_gain", "sum"),
    max_speed=("max_speed", "max"),
    average_speed=("average_speed", "mean"),
)

annual_cycling["average_speed_weighted"] = activities.groupby(
    activities["start_date"].dt.tz_convert(None).dt.to_period("Y")
).apply(lambda x: (x["average_speed"] * x["distance"]).sum() / x["distance"].sum())

annual_cycling = convert_units(
    annual_cycling,
    rounding_digits=1,
).reset_index(drop=False)
annual_cycling["start_date"] = annual_cycling["start_date"].astype(str).astype(int)
annual_cycling = annual_cycling.sort_values("start_date", ascending=False)
annual_cycling_viz = annual_cycling.rename(columns=col_rename_dict)

# Final cleaning of table column (needs to be after generating cumulative distance)
activities_viz = activities_ready.copy()
activities_viz["start_date"] = activities_viz["start_date"].dt.strftime("%B %d, %Y")
activities_viz["sport_type"] = activities_viz["sport_type"].replace(activity_mapping)
activities_viz = activities_viz.rename(columns=col_rename_dict)


# Set templates
pio.templates.default = "simple_white"

# Set styles
tab_style = {"font_size": "1.1rem"}
selected_tab_style = {
    "font_size": "1.1rem",
    "fontWeight": "bold",
}

# Creating graphs

# Last activity cards

metrics = [
    "Distance [km]",
    "Elevation [m]",
    "Avg. speed [km/h]",
    "Max. speed [km/h]",
    "Wt. avg. watts",
    "Max. watts",
    "Avg. cadence [rpm]",
    "Temperatur °C",
]
cards = [
    get_metric_card(
        df=activities_viz,
        metric=metric,
        sport_type=activities_viz.head(1)["Type"].iloc[0],
        reference_year=current_year,
    )
    for metric in metrics
]

# Line graph of cumulative distance (current year)
fig_annual_cumsum = px.line(
    activities_ready.query("sport_type in ['Ride', 'MountainBikeRide', 'VirtualRide']"),
    x="start_date_current_year",
    y="annual_cumulative_distance",
    color="start_year",
    color_discrete_sequence=px.colors.qualitative.G10,
    hover_data=["start_year", "annual_cumulative_distance"],
)

# Adding line graph of cumulative distance (all previous years)

# fig_annual_cumsum.add_scatter(
#     x=activities_ready.query("start_year == @current_year")["start_date_current_year"],
#     y=activities_ready.query("start_year == @current_year")[
#         "annual_cumulative_distance"
#     ],
#     mode="lines",
#     line=dict(color=px.colors.sequential.Blues[-1]),
# )
fig_annual_cumsum.update_layout(
    yaxis=dict(title=f"Annual cumulative Distance (km)"),
    legend=dict(
        x=0.03,  # Place at the right side of the plot area
        y=0.95,  # Place at the bottom side of the plot area
        xanchor="left",  # Anchor the legend to the right
        yanchor="top",  # Anchor the legend to the bottom
    ),
)
update_date_axis(fig_annual_cumsum, start_date, end_date, freq="MS")


# NOTE DEPRECATED
# fig_annual_cumsum.add_scatter(
#     x=goal_dates,  # The date range for the goal
#     y=goal_distances,  # The cumulative goal distance
#     mode="lines",
#     name=f"Reference line for annual aim ({total_goal_distance} km)",  # Label for the goal line
#     line=dict(color="grey", dash="dash"),  # Customize the line style (red, dashed)
# )

# Creating heatmap
generate_folium_map(
    activities,
    "heatmap_all_activities.html",
    "Sport type",
    5,
    "median",
    # (49.37, 8.78),  # Heidelberg
)

generate_folium_map(
    activities.head(1),
    "last_activity.html",
    "Last activity",
    11,
    "last",
)


# Initialize the Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
server = app.server  # Expose the Flask server instance for WSGI servers
app.layout = html.Div(
    [
        # Top container fills the viewport minus the bottom fixed container.
        dbc.Container(
            [
                # Tabs row (non-scrolling). If there are many tabs horizontally this
                # wrapper allows horizontal scrolling of the tabs themselves.
                dbc.Row(
                    dbc.Col(
                        html.Div(
                            dcc.Tabs(
                                id="tabs",
                                value="lifetime",
                                children=[
                                    dcc.Tab(
                                        label="Activities (lifetime)",
                                        value="lifetime",
                                        style=tab_style,
                                        selected_style=selected_tab_style,
                                    ),
                                    dcc.Tab(
                                        label="Last activity",
                                        value="last",
                                        style=tab_style,
                                        selected_style=selected_tab_style,
                                    ),
                                    dcc.Tab(
                                        label="Annual cycling overview",
                                        value="annual_overview",
                                        style=tab_style,
                                        selected_style=selected_tab_style,
                                    ),
                                    dcc.Tab(
                                        label="Metrics comparison",
                                        value="metrics_comparison",
                                        style=tab_style,
                                        selected_style=selected_tab_style,
                                    ),
                                ],
                                # tabs styling: horizontal + allow horizontal scroll if many tabs
                                style={
                                    "display": "flex",
                                    "flexDirection": "row",
                                    "width": "100%",
                                    "overflowX": "auto",
                                    "whiteSpace": "nowrap",
                                },
                            ),
                            # keep the tabs visually separated from the content
                            style={"backgroundColor": "white", "padding": "0.25rem"},
                        ),
                        width=12,
                    ),
                    # ensure row does not grow/shrink (so the content area is the scroller)
                    style={"flex": "0 0 auto"},
                ),
                # Scrollable content area — this is the only area that scrolls
                dbc.Row(
                    dbc.Col(
                        # set the inner div to take full height and be scrollable
                        html.Div(
                            id="tabs-content",
                            style={
                                "height": "100%",
                                "overflowY": "auto",
                                "padding": "1rem",
                            },
                        ),
                        width=12,
                        style={"height": "100%"},
                    ),
                    # make this row expand to fill remaining vertical space
                    style={"flex": "1 1 auto", "minHeight": 0},
                ),
            ],
            fluid=True,
            # crucial: make this container fill the viewport minus the fixed bottom bar
            style={
                "display": "flex",
                "flexDirection": "column",
                "height": f"calc(100vh)",
                "paddingTop": "0",
                "paddingBottom": "0",
            },
        ),
        # Bottom container (unchanged) — fixed to viewport bottom
        dbc.Container(
            [
                dbc.Row(
                    html.P(
                        [
                            "Source code",
                            html.A(
                                "https://github.com/TobiasAnh/myactivities",
                                href="https://github.com/TobiasAnh/myactivities",
                                target="_blank",
                            ),
                        ],
                        style={
                            "text-align": "center",
                            "margin-top": "0px",
                            "margin-bottom": "0px",
                        },
                    )
                ),
            ],
            className="fixed-bottom bg-light p-2",
        ),
    ]
)


# Callback to update content based on selected tab
@app.callback(
    dash.dependencies.Output("tabs-content", "children"),
    [dash.dependencies.Input("tabs", "value")],
)
def render_content(tab):
    if tab == "last":

        return html.Div(
            [
                html.Iframe(
                    srcDoc=open(
                        "last_activity.html", "r"
                    ).read(),  # Load the saved HTML file
                    width="100%",  # Width of the map
                    height="600",  # Height of the map
                ),
                dbc.Row(
                    [dbc.Col(card, width="auto") for card in cards], justify="around"
                ),
                # NOTE DEPRECATED TABLE
                # dash_table.DataTable(
                #     id="table_activities",
                #     columns=[{"name": i, "id": i} for i in activities_viz.columns],
                #     data=activities_viz.head(1).to_dict("records"),
                #     style_table={"width": "100%", "margin": "auto"},
                #     style_cell={"textAlign": "right"},
                #     style_header={"fontWeight": "bold"},
                #     # Enable sorting, filtering, and pagination
                #     sort_action="native",
                #     # filter_action="native",
                #     page_action="native",
                #     page_size=100,  # Show 5 row sper page
                # ),
            ]
        )
    elif tab == "lifetime":
        return html.Div(
            [
                html.Iframe(
                    srcDoc=open(
                        "heatmap_all_activities.html", "r"
                    ).read(),  # Load the saved HTML file
                    width="100%",  # Width of the map
                    height="600",  # Height of the map
                ),
                dash_table.DataTable(
                    id="table_activities",
                    columns=[
                        {"name": i, "id": i}
                        for i in activities_viz[columns_shorter].columns
                    ],
                    data=activities_viz[columns_shorter].to_dict("records"),
                    style_table={"width": "100%", "margin": "auto"},
                    style_cell={"textAlign": "right"},
                    style_header={"fontWeight": "bold"},
                    # Enable sorting, filtering, and pagination
                    sort_action="native",
                    # filter_action="native",
                    page_action="native",
                    page_size=5,  # Show 5 row sper page
                ),
            ]
        )
    elif tab == "annual_overview":
        return html.Div(
            [
                dcc.Graph(
                    id="annual_summary_graph",
                    figure=fig_annual_cumsum,
                    style={"width": "100%", "height": "600px"},
                ),
                dash_table.DataTable(
                    id="table_annual_summaries",
                    columns=[{"name": i, "id": i} for i in annual_cycling_viz.columns],
                    data=annual_cycling_viz.to_dict("records"),
                    style_table={"width": "100%", "margin": "auto"},
                    style_cell={"textAlign": "right"},
                    style_header={"fontWeight": "bold"},
                    # Enable sorting, filtering, and pagination
                    # sort_action="native",
                    # filter_action="native",
                    page_action="native",
                    page_size=5,
                ),
            ]
        )
    elif tab == "metrics_comparison":
        return html.Div(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label(
                                    "Select Y-value", style={"fontWeight": "bold"}
                                ),
                                dcc.Dropdown(
                                    id="metrics_y_dropdown",
                                    options=[{"label": m, "value": m} for m in metrics],
                                    value="Elevation [m]",
                                    clearable=False,
                                ),
                            ],
                            width=6,  # takes half the row on medium+ screens, full width on small
                        ),
                        dbc.Col(
                            [
                                html.Label(
                                    "Select X-value", style={"fontWeight": "bold"}
                                ),
                                dcc.Dropdown(
                                    id="metrics_x_dropdown",
                                    options=[{"label": m, "value": m} for m in metrics],
                                    value="Distance [km]",
                                    clearable=False,
                                ),
                            ],
                            width=6,
                        ),
                    ],
                    justify="center",  # horizontally center the row
                    className="mb-3",  # margin below
                ),
                dcc.Graph(id="fig_metrics_comparison"),
            ]
        )


@app.callback(
    dash.dependencies.Output("fig_metrics_comparison", "figure"),
    [
        dash.dependencies.Input("metrics_y_dropdown", "value"),
        dash.dependencies.Input("metrics_x_dropdown", "value"),
    ],
)
def update_metrics_graph(y_metric, x_metric):
    df = activities_viz.query("Type == 'Road bike'")
    fig_metrics_comparison = px.scatter(
        df,
        x=x_metric,
        y=y_metric,
        # range_x=[
        #     df[x_metric].min(),
        #     df[x_metric].max(),
        # ],
        # range_y=[
        #     df[y_metric].min(),
        #     df[y_metric].max(),
        # ],
        # # color="Temperatur °C",
        # color_discrete_sequence=px.colors.qualitative.G10,
        hover_data=["Date", "Name"],
    )
    fig_metrics_comparison.update_traces(mode="markers")

    return fig_metrics_comparison


# Run the app
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)
