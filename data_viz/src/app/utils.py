from dotenv import load_dotenv, find_dotenv
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
import numpy as np
import pandas as pd
import ast
import logging
import polyline
import plotly.graph_objects as go
import folium

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env variables
# Load env variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)


columns_shorter = [
    "start_date",
    "sport_type",
    "name",
    "distance",
    "moving_time",
    # "elapsed_time",
    "total_elevation_gain",
    "average_speed",
    "max_speed",
]

# Columns for dash
columns_short = [
    "name",
    "distance",
    "moving_time",
    "elapsed_time",
    "total_elevation_gain",
    "sport_type",
    "start_date",
    # "start_date_local",
    # "achievement_count",
    # "kudos_count",
    # "athlete_count",
    # "photo_count",
    "start_latlng",
    "end_latlng",
    "average_speed",
    "max_speed",
    "average_cadence",
    "average_temp",
    "average_watts",
    "max_watts",
    "weighted_average_watts",
    "kilojoules",
    "elev_high",
    "elev_low",
    # "pr_count",
    # "total_photo_count",
    # "map_id",
    # "summary_polyline",
]

col_rename_dict = {
    "start_date": "Date",
    "activities_type": "Type",
    "sport_type": "Type",
    "name": "Name",
    "total_distance": "Distance [km]",
    "distance": "Distance [km]",
    "total_moving_time": "Moving time",
    "moving_time": "Moving time",
    "total_elevation_gain": "Elevation [m]",
    "average_speed": "Avg. speed [km/h]",
    "max_speed": "Max. speed [km/h]",
    "n_activities": "Activities (n)",
    "average_speed_weighted": "Wt. avg. speed [km/h]",
}

# TODO is mapped two times (see also legend below)
activity_mapping = {
    "Ride": "Road bike",
    "MountainBikeRide": "MTB",
}


def get_engine():
    """
    Create and return a SQLAlchemy engine for a PostgreSQL database.
    Loads credentials from a .env file and builds the connection string.

    Returns:
        Engine: SQLAlchemy engine connected to the specified database.
    """

    try:

        DATABASE_USER = os.environ["POSTGRES_USER"]
        DATABASE_PASSWORD = os.environ["POSTGRES_PASSWORD"]
        DATABASE_HOST = "postgres"  # This should match your Docker Compose service name
        DATABASE_PORT = os.environ["POSTGRES_PORT"]
        DATABASE_NAME = os.environ["POSTGRES_DB"]

        # Create the engine using the credentials from the .env file
        engine = create_engine(
            f"postgresql+psycopg2://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
        )
        return engine

    except KeyError as e:
        logger.error(
            f"Error: Missing environment variable {e}. Please check your .env file."
        )
        return None
    except Exception as e:
        logger.error(f"An error occurred while creating the engine: {e}")
        return None


def fetch_data(engine, query, index_col=None):
    """
    Fetches data from a PostgreSQL database using a SQLAlchemy engine.

    This function attempts to execute a given SQL query and returns the result
    as a pandas DataFrame. It includes comprehensive error handling for common issues.

    Args:
        engine (Engine): The SQLAlchemy engine connected to the database.
        query (str): The SQL query string to be executed.
        index_col (str, optional): Column to set as the index of the DataFrame.
                                   Defaults to None.

    Returns:
        pd.DataFrame | None: A pandas DataFrame containing the query results,
                             or None if an error occurred.
    """
    if not isinstance(query, str) or not query.strip():
        logger.error("Invalid query provided. Query must be a non-empty string.")
        return None

    try:
        logger.info("Attempting to connect to the database...")
        with engine.connect() as connection:
            logger.info(f"Executing query: {query[:50]}...")
            df = pd.read_sql(query, connection, index_col=index_col)
            logger.info("Query executed successfully.")
            if not df.empty:
                return df
            else:
                logger.info("DataFrame empty.")
                return None

    except SQLAlchemyError as e:
        logger.error(f"Database error during query execution: {e}")
        # Log specific details about the error for debugging
        if "connection" in str(e).lower():
            logger.error(
                "This may be a connection issue. Check your database credentials and availability."
            )
        return None
    except ImportError as e:
        logger.error(
            f"Missing a required library: {e}. Please ensure pandas and sqlalchemy are installed."
        )
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred while fetching data: {e}")
        return None


def generate_folium_map(
    activities,
    file_name,
    legend_name,
    zoom_start,
    lat_lon="last",
    marker_opacity=0.5,
):
    """
    Generate an interactive Folium map of activities. Saves it as .html file in root repo.

    Plots activity routes from encoded polylines with sport-specific colors
    and adds a legend based on sport type.

    Parameters:
        activities (DataFrame): Activity data containing at least
            'summary_polyline' and 'sport_type' columns.
        file_name (str): Name of the output HTML file.
        legend_name (str): Title for the legend.
        zoom_start (int): Initial zoom level of the map.
        lat_lon (tuple[float, float] | str, optional): Map center.
            - Provide a (latitude, longitude) tuple to set manually.
            - Use "median" to center on the median location of all activities.
            - Use "last" (default) to center on the most recent activity.
        marker_opacity (float, optional): Opacity of heatmap markers.
            Defaults to 0.5.
    """

    activities = activities.copy()

    # Check coordinates
    if lat_lon == "median":
        activities["start_latlng"] = activities["start_latlng"].apply(ast.literal_eval)
        lats = (
            activities["start_latlng"]
            .apply(lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None)
            .to_list()
        )
        lons = (
            activities["start_latlng"]
            .apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else None)
            .to_list()
        )
        lat_lon = (np.nanmedian(lats), np.nanmedian(lons))

    elif lat_lon == "last":
        coordinates = polyline.decode(activities["summary_polyline"].iloc[0])
        lats = [lat for lat, lon in coordinates]
        lons = [lon for lat, lon in coordinates]
        lat_lon = (np.nanmean(lats), np.nanmean(lons))

    elif (
        isinstance(lat_lon, tuple)
        and len(lat_lon) == 2
        and all(isinstance(x, (int, float)) for x in lat_lon)
    ):
        lat_lon = lat_lon

    else:
        logger.info(
            "lat_lon argument set incorrectly. Pleae provide tuple with numeric coordinates or 'average' or 'last'"
        )

    mymap = folium.Map(
        location=lat_lon,
        tiles="CartoDB Positron",  # map style
        zoom_start=zoom_start,
    )

    # Dictionary to hold the colors and labels for the legend
    legend_items = {}

    for activity in activities.index:
        activity_data = activities.loc[activity]
        activity_polyline = activity_data["summary_polyline"]

        try:
            coordinates = polyline.decode(activity_polyline)
        except Exception as e:
            print(f"Error decoding polyline")
            print(f"Error details: {e}")
            print()
            print(activity)
            print()
            continue

        sport_type = activity_data["sport_type"]

        # Determine the color based on sport type
        if sport_type == "Ride":
            color = "#1f78b4"
            label = "Road bike"
        elif sport_type == "MountainBikeRide":
            color = "#ff7f00"
            label = "MTB"
        elif sport_type == "Hike":
            color = "#33a02c"
            label = sport_type
        elif sport_type == "VirtualRide":
            color = "#6a3d9a"
            label = sport_type
        else:
            color = "#e31a1c"
            label = "Other"

        # Add the color and label to our legend dictionary if it's not already there
        legend_items[label] = color

        # Popup/tooltip
        date_str = str(activity_data["start_date"])[:10]
        popup_tooltip = f"{date_str} | {activity_data['name']}"
        # Add a PolyLine to connect the coordinates
        folium.PolyLine(
            coordinates,
            popup=popup_tooltip,
            tooltip=popup_tooltip,
            color=color,
            weight=2.5,
            opacity=marker_opacity,
        ).add_to(mymap)

    # --- Create the custom legend HTML ---
    # We will build the legend dynamically based on the sport types found
    # in the data.

    legend_html_items = ""
    for label, color in legend_items.items():
        legend_html_items += f"""
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
              <div style="width: 20px; height: 10px; background-color: {color}; margin-right: 5px;"></div>
              {label}
            </div>
        """

    legend_html = f"""
     <div style="position: fixed; 
                 top: 10px; right: 10px; 
                 width: auto; height: auto; 
                 border: 2px solid grey; 
                 z-index:9999; font-size:14px;
                 background-color: white;
                 opacity: 0.9;">
       <div style="background-color: #f0f0f0; padding: 5px; text-align: center; font-weight: bold;">
         {legend_name}
       </div>
       <div style="padding: 10px;">
         {legend_html_items}
       </div>
     </div>
     """

    # Add the HTML legend to the map
    mymap.get_root().html.add_child(folium.Element(legend_html))

    # Save the map to an HTML file
    mymap.save(file_name)


def findColumns(df, search_term):
    found_columns = [col for col in df.columns if search_term in col]
    # print(f"Found {len(found_columns)} columns having {search_term} in name")
    return found_columns


def convert_units(df, rounding_digits=0):
    df = df.copy()

    # Convert distance from meters to kilometers and overwrite column
    distance_cols = findColumns(df, "distance")
    for distance_col in distance_cols:
        df[distance_col] = round(df[distance_col] / 1000, rounding_digits)

    # Convert moving_time (seconds) to timedelta and then to minutes, overwrite the column
    time_cols = findColumns(df, "_time")
    for time_col in time_cols:
        df[time_col] = pd.to_timedelta(df[time_col], unit="s")
        df[time_col] = df[time_col].apply(
            lambda x: f"{x.components.days} days {x.components.hours:02}:{x.components.minutes:02}"
        )

    # Convert speed from m/s to km/h and overwrite the columns
    speed_cols = findColumns(df, "_speed")
    for speed_col in speed_cols:
        df[speed_col] = round(df[speed_col] * 3.6, rounding_digits)

    # Rounding elevation gain
    df["total_elevation_gain"] = round(df["total_elevation_gain"], rounding_digits)

    return df
