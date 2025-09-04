import webbrowser
import requests
import json
import os
import logging
import time
import pytz
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base url
BASE_URL = "https://www.strava.com/api/v3/"


def get_tokens(refresh_token=None):

    CLIENT_ID = os.environ["CLIENT_ID"]
    CLIENT_SECRET = os.environ["CLIENT_SECRET"]

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    if not refresh_token:
        authorization_url = get_strava_authorization_url(CLIENT_ID)
        webbrowser.open(authorization_url)
        code = input(
            "Look at your browser. Enter the code you received after authorization: "
        )
        code = code.strip()
        payload.update(
            {
                "code": code,
                "grant_type": "authorization_code",
            }
        )

    else:
        payload.update(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )

    response = requests.post("https://www.strava.com/api/v3/oauth/token", data=payload)
    if response.status_code == 200:
        response_dict = response.json()

        return (
            response_dict["access_token"],
            response_dict["refresh_token"],
            response_dict["expires_at"],
        )
    else:
        logger.info("reponse not 200")


def get_strava_authorization_url(
    client_id,
    redirect_uri="http://localhost/exchange_token",
    scopes=["activity:read"],
):
    base_url = "https://www.strava.com/oauth/authorize"
    scope_str = ",".join(scopes)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "force",  # force / auto
        "scope": scope_str,
    }
    request_url = requests.Request("GET", base_url, params=params).prepare().url
    return request_url


def get_athlete_info(access_token):
    logger.info("Extracting athlete information ... ")
    url = f"{BASE_URL}athlete"
    athlete = make_request(url, access_token)
    return athlete


def get_activities(access_token, athlete, start_unix=None):

    end_unix = int(time.time())

    activities = []
    page = 1
    while True:
        url = f"{BASE_URL}athlete/activities?before={end_unix}&after={start_unix}&page={page}&per_page=30"
        page_respond = make_request(url, access_token)
        if not page_respond:
            break

        activities.extend(page_respond)
        logger.info(f"Found {page} pages of activities.")
        page += 1

        # TODO break just temporarily
        break

    if not activities:
        logger.info("No recent activities found. Database seems up to date!")
    else:
        logger.info(f"Found {len(activities)} new activities")

    return activities


def create_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info(f"{filepath} has been created or updated")


def import_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Imported data from {filepath}")
        return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None


def make_request(url, access_token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.error(f"HTTP error {response.status_code}: {response.reason}")
        return None
    return response.json()


def convert_str_to_unix(date_str, assign_to_utc=True):
    if not date_str:
        logger.info("No time found")
    if assign_to_utc:
        naive_datetime = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        utc_datetime = pytz.utc.localize(naive_datetime)

    unix_utc_timestamp = int(utc_datetime.timestamp())

    return unix_utc_timestamp


# POSTGRES functions


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


# Get the latest start_date from the activities table
def get_latest_datetime(datetime_col, table):
    """Query postgresql database to find the latest start_date."""

    try:
        engine = get_engine()
        with engine.connect() as connection:
            result = connection.execute(
                text(f"SELECT MAX({datetime_col}) FROM {table};")
            )
            latest_datetime = result.scalar()  # Get the single scalar value
            logger.info(
                f"Latest {datetime_col} in postgresql table >> {table} <<: {latest_datetime}"
            )
            return convert_str_to_unix(latest_datetime)

    except ProgrammingError:
        logger.info(f"Postgresql {table} not found. Setting latest_datetime manually.")
        return 1388530800  # timestamp refers to 2014


def create_table_with_schema(schema_file):
    """Load the SQL schema from a file and execute it."""
    try:
        with open(schema_file, "r") as file:
            schema_sql = file.read()

        # Split commands by semicolon if multiple statements exist
        commands = schema_sql.strip().split(";")

        engine = get_engine()
        if engine is None:
            logger.error("Engine could not be created. Aborting.")
            return

        with engine.connect() as connection:
            for command in commands:
                command = command.strip()
                if command:
                    logger.info(f"Executing SQL command: {command[:50]}...")
                    connection.execute(text(command))
            connection.commit()  # ensure DDL statements are applied

        engine.dispose()

    except FileNotFoundError:
        logger.error(f"Schema file not found: {schema_file}")
    except Exception as e:
        logger.error(f"Error executing schema: {e}")
