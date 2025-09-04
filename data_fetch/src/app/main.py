import pandas as pd
import time
import argparse
import os
import logging
from app.utils import (
    create_table_with_schema,
    get_tokens,
    get_engine,
    get_athlete_info,
    get_activities,
)


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(mode):

    # Generate postgres tables
    create_table_with_schema("src/app/athlete.sql")
    create_table_with_schema("src/app/activities.sql")

    # Get API Credentials from .env file
    ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
    REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]
    TOKEN_EXPIRATION = int(os.environ["TOKEN_EXPIRATION"])

    if int(time.time()) > TOKEN_EXPIRATION:
        logger.info("Access token expired ...  ")
        if REFRESH_TOKEN:
            logger.info(f"Refresh token found. Getting new access token ... ")

            ACCESS_TOKEN, REFRESH_TOKEN, TOKEN_EXPIRATION = get_tokens(REFRESH_TOKEN)
            # print(ACCESS_TOKEN, REFRESH_TOKEN, TOKEN_EXPIRATION)

    else:
        logger.info("Access token not expired ...  ")

    # Fetch athlete data
    athlete = get_athlete_info(ACCESS_TOKEN)

    # ATHLETE
    # df = pd.DataFrame.from_dict(athlete, orient="index").T
    # df = df.rename(columns={"id": "athlete_id"})
    # df = df.set_index("athlete_id")
    # engine = get_engine()
    # df.to_sql(
    #     "athlete",
    #     con=engine,
    #     if_exists="replace",
    #     index=True,
    # )

    # # ACTIVITIES
    # start_unix = get_latest_datetime("start_date", "activities")
    # activities = get_activities(
    #     ACCESS_TOKEN,
    #     athlete,
    #     start_unix=start_unix,
    # )

    # if not activities:
    #     return
    # df = pd.DataFrame(activities)

    # df[["map_id", "summary_polyline", "map_resource_state"]] = df["map"].apply(
    #     pd.Series
    # )
    # df = df.rename(columns={"type": "activities_type", "id": "activity_id"})
    # df = df.drop(["map"], axis=1)

    # # NOTE for some reason, the .to_sql only works when saving and reloading the csv.
    # # Save and load csv
    # df.to_csv("activities.csv", index=False)
    # df = pd.read_csv(
    #     "activities.csv",
    #     index_col="activity_id",
    # )

    df = pd.read_csv(
        "src/app/activities.csv",
        index_col="activity_id",
    )

    # Move date to postgres database
    engine = get_engine()
    try:
        df.to_sql(
            "activities",
            con=engine,
            if_exists="replace",  # TODO switch in production back to append
            index=True,
        )
    except ValueError as e:
        print(e)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Process some modes.")
    parser.add_argument(
        "--mode",
        type=str,
        default="update",
        choices=["update", "init"],
        help='Mode of operation: "update" (default) or "init".',
    )

    args = parser.parse_args()
    main(args.mode)
