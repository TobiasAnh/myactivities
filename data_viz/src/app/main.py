import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import logging
from dash import dcc, html, dash_table
from datetime import datetime
from app.utils import (
    columns_short,
    columns_shorter,
    get_engine,
    fetch_data,
    convert_units,
    generate_folium_map,
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
total_goal_distance = 8000  # NOTE Hardcoded
daily_distance_goal = total_goal_distance / days_in_year  # km/day
goal_dates = pd.date_range(start_date, end_date, freq="D")
goal_distances = daily_distance_goal * (goal_dates - start_date).days


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


# Tidy up activities dataframe
activities["start_date"] = pd.to_datetime(activities["start_date"])
activities = activities.sort_values("start_date", ascending=False)
activities_ready = convert_units(activities[columns_shorter], rounding_digits=1)
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


# Creating df of annual summaries
annual_summaries = activities.groupby(
    activities["start_date"].dt.tz_convert(None).dt.to_period("Y")
).agg(
    n_activities=("resource_state", "size"),
    total_distance=("distance", "sum"),
    total_moving_time=("moving_time", "sum"),
    total_elapsed_time=("elapsed_time", "sum"),
    total_elevation_gain=("total_elevation_gain", "sum"),
    max_speed=("max_speed", "max"),
    average_speed=("average_speed", "mean"),
)

annual_summaries["average_speed_weighted"] = activities.groupby(
    activities["start_date"].dt.tz_convert(None).dt.to_period("Y")
).apply(lambda x: (x["average_speed"] * x["distance"]).sum() / x["distance"].sum())

annual_summaries = convert_units(annual_summaries, rounding_digits=1)
annual_summaries = annual_summaries.reset_index(drop=False)
annual_summaries["start_date"] = annual_summaries["start_date"].astype(str).astype(int)
annual_summaries_ready = annual_summaries.sort_values("start_date", ascending=False)


# Creating graphs

# Line graph of cumulative distance per year
fig_annual_cumsum = px.line(
    activities_ready.query("start_year == @current_year"),
    x="start_date",  # Adjust column name if needed
    y="annual_cumulative_distance",
    # color="start_year",  # Adjust this to a numeric column you want to plot
    # title=f"Cumulate km of rides for {current_year}",
)

fig_annual_cumsum.update_layout(
    xaxis=dict(
        title=None,
        range=[start_date, end_date],  # Full year range on x-axis
        tickformat="%b",  # Show month abbreviations on the x-axis
        tickmode="array",  # Specify custom ticks
        tickvals=pd.date_range(
            start=start_date, end=end_date, freq="MS"
        ),  # First of every month
        ticktext=[
            date.strftime("%b")
            for date in pd.date_range(start=start_date, end=end_date, freq="MS")
        ],  # Month names
    ),
    yaxis=dict(title=f"Cumulative Distance (km) in {current_year}"),
    legend=dict(
        x=0.03,  # Place at the right side of the plot area
        y=0.95,  # Place at the bottom side of the plot area
        xanchor="left",  # Anchor the legend to the right
        yanchor="top",  # Anchor the legend to the bottom
    ),
)

fig_annual_cumsum.add_scatter(
    x=goal_dates,  # The date range for the goal
    y=goal_distances,  # The cumulative goal distance
    mode="lines",
    name=f"Reference line for annual aim ({total_goal_distance} km)",  # Label for the goal line
    line=dict(color="grey", dash="dash"),  # Customize the line style (red, dashed)
)

# Creating heatmap

generate_folium_map(
    activities,
    "src/heatmaps/heatmap_all_activities.html",
    "Activity type",
    5,
    (49.37, 8.78),  # Heidelberg
)

generate_folium_map(
    activities.head(1),
    "src/heatmaps/last_activity.html",
    "Last activity",
    12,
    lat_lon="auto",
)


# Final cleaning of table column (needs to be after generating cumulative distance)
activities_ready["start_date"] = activities_ready["start_date"].dt.strftime("%B %d, %Y")


# Initialize the Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server  # Expose the Flask server instance for WSGI servers

# Layout of the app
app.layout = html.Div(
    [
        dbc.Container(
            [
                dbc.Row(
                    dbc.Col(
                        html.H3(
                            f"Strava activities of {athlete['firstname'].values}",
                            style={"text-align": "center"},
                        ),
                    )
                ),
                dbc.Row(
                    dbc.Col(
                        html.Div(
                            [
                                dcc.Tabs(
                                    id="tabs",
                                    value="lifetime",
                                    children=[
                                        dcc.Tab(
                                            label="Activities (lifetime)",
                                            value="lifetime",
                                        ),
                                        dcc.Tab(
                                            label="Activities (last one)",
                                            value="last",
                                        ),
                                        dcc.Tab(
                                            label="Annual overview",
                                            value="annual_overview",
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "flex-direction": "row",  # Horizontal tabs
                                        "width": "100%",
                                    },
                                ),
                                html.Div(id="tabs-content", style={"width": "100%"}),
                            ],
                        ),
                        width="100%",  # Full width
                    )
                ),
            ],
            fluid=True,  # Improved responsiveness
        ),
        dbc.Container(
            [
                dbc.Row(
                    html.P(
                        [
                            "Source code dashboard: ",
                            html.A(
                                "https://github.com/TobiasAnh/strava_dash",
                                href="https://github.com/TobiasAnh/strava_dash",
                                target="_blank",  # This opens the link in a new tab
                            ),
                            " | ",
                            "Source code underlying data pipeline: ",
                            html.A(
                                "https://github.com/TobiasAnh/strava_analysis",
                                href="https://github.com/TobiasAnh/strava_analysis",
                                target="_blank",  # This opens the link in a new tab
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
            className="fixed-bottom bg-light p-2",  # This is the key part for styling
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
        # Content for the first tab
        return html.Div(
            [
                html.Iframe(
                    srcDoc=open(
                        "src/heatmaps/last_activity.html", "r"
                    ).read(),  # Load the saved HTML file
                    width="100%",  # Width of the map
                    height="600",  # Height of the map
                ),
                dash_table.DataTable(
                    id="table_activities",
                    columns=[{"name": i, "id": i} for i in activities_ready.columns],
                    data=activities_ready.head(1).to_dict("records"),
                    style_table={"width": "100%", "margin": "auto"},
                    style_cell={"textAlign": "right"},
                    style_header={"fontWeight": "bold"},
                    # Enable sorting, filtering, and pagination
                    sort_action="native",
                    # filter_action="native",
                    page_action="native",
                    page_size=100,  # Show 5 row sper page
                ),
            ]
        )
    elif tab == "lifetime":
        return html.Div(
            [
                html.Iframe(
                    srcDoc=open(
                        "src/heatmaps/heatmap_all_activities.html", "r"
                    ).read(),  # Load the saved HTML file
                    width="100%",  # Width of the map
                    height="600",  # Height of the map
                ),
                dash_table.DataTable(
                    id="table_activities",
                    columns=[{"name": i, "id": i} for i in activities_ready.columns],
                    data=activities_ready.to_dict("records"),
                    style_table={"width": "100%", "margin": "auto"},
                    style_cell={"textAlign": "right"},
                    style_header={"fontWeight": "bold"},
                    # Enable sorting, filtering, and pagination
                    sort_action="native",
                    # filter_action="native",
                    page_action="native",
                    page_size=10,  # Show 5 row sper page
                ),
            ]
        )
    elif tab == "annual_overview":
        # Placeholder content for the new tab
        return html.Div(
            [
                dcc.Graph(
                    id="annual_summary_graph",
                    figure=fig_annual_cumsum,
                    style={"width": "100%", "height": "400px"},
                ),
                dash_table.DataTable(
                    id="table_annual_summaries",
                    columns=[
                        {"name": i, "id": i} for i in annual_summaries_ready.columns
                    ],
                    data=annual_summaries_ready.to_dict("records"),
                    style_table={"width": "100%", "margin": "auto"},
                    style_cell={"textAlign": "right"},
                    style_header={"fontWeight": "bold"},
                    # Enable sorting, filtering, and pagination
                    # sort_action="native",
                    # filter_action="native",
                    page_action="native",
                    page_size=100,  # Show 5 rows per page
                ),
            ]
        )


# Run the app
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)
