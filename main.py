import datetime
import json
import math
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

import requests
import argparse

@dataclass
class PropertyData:
    street_address: str
    city: str
    state: str
    zipcode: str
    price: str
    sqft: float
    beds: float
    baths: float
    url: str
    listed: datetime.datetime


# https://rapidapi.com/apidojo/api/realtor/

RAPIDAPI_HOST = "realtor.p.rapidapi.com"
URL = f"https://{RAPIDAPI_HOST}/properties/v3/list"
LIMIT = 20
CONFIG_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "config.json")
NOW = datetime.datetime.now()


def optimistic_float_to_int(value: float) -> int | float:
    """
    Converts a float to an int if nothing would be lost
    """
    return int(value) if value - math.floor(value) == 0 else value


def parse_datetime(value: str) -> datetime.datetime:
    """
    Takes a string and tries to convert it to a datetime
    """
    if value.endswith("Z"):
        value = value.removesuffix("Z")

    return datetime.datetime.fromisoformat(value)


def send_email(config_data: dict, message_text: str) -> None:
    """
    Send an email with the given message
    """

    print("Sending email")

    server = smtplib.SMTP(config_data["SMTP"]["SERVER"], config_data["SMTP"]["PORT"])

    try:
        # prepare sever connection
        context = ssl.create_default_context()
        server.starttls(context=context)
        server.login(config_data["SMTP"]["USER"], config_data["SMTP"]["PASS"])

        # build message
        message = EmailMessage()
        message.set_content(message_text)
        message["Subject"] = f'Daily Realtor Update: {NOW.strftime("%Y-%m-%d")}'
        message["From"] = f'Daily Realtor <{config_data["SMTP"]["FROM"]}>'
        message["To"] = config_data["DEST_EMAIL"]

        # send message
        server.send_message(message)

    except Exception as e:
        print("Unable to send email")
        print(e)
    finally:
        server.quit()


def parse_property_list(data: dict) -> list[PropertyData]:
    """
    Parse JSON data of search results and create a list of data classes.
    """

    output = []

    for property in data["data"]["home_search"]["results"]:
        # test if list time time is sooner than one day ago
        list_datetime = parse_datetime(property["list_date"])
        if NOW - list_datetime > datetime.timedelta(days=1):
            continue

        # parse
        address = property["location"]["address"]
        description = property["description"]

        # convert none to 0
        baths_full = description["baths_full"]
        if baths_full is None:
            baths_full = 0

        baths_half = description["baths_half"]
        if baths_half is None:
            baths_half = 0

        output.append(
            PropertyData(
                street_address=address["line"],
                city=address["city"],
                state=address["state_code"],
                zipcode=address["postal_code"],
                price="${:,}".format(property["list_price"]),
                sqft=description["sqft"],
                beds=description["beds"],
                baths=optimistic_float_to_int(baths_full + 0.5 * baths_half),
                url=property["href"],
                listed=list_datetime,
            )
        )

    return output


def create_property_table(property_data_list: list[PropertyData]) -> str:
    """
    Create a string represenation of a table of data
    """
    # location_table = prettytable.PrettyTable()
    # location_table.field_names = [
    #     "Price",
    #     "Address",
    #     "Square Feet",
    #     "Beds/Baths",
    #     "URL",
    #     "Listed",
    # ]
    # location_table.align = "r"
    # location_table.align["URL"] = "l"  # type: ignore
    # location_table.set_style(prettytable.SINGLE_BORDER)

    # for pd in property_data_list:
    #     # check if items are known
    #     sqft = pd.sqft
    #     if sqft is None or sqft == 0:
    #         sqft = "???"

    #     beds = pd.beds
    #     if beds is None or beds == 0:
    #         beds = "?"

    #     baths = pd.baths
    #     if baths is None or baths == 0:
    #         baths = "?"

    #     # add row to table
    #     location_table.add_row(
    #         [
    #             pd.price,
    #             f"{pd.street_address}, {pd.city}, {pd.state} {pd.zipcode}",
    #             sqft,
    #             f"{beds}/{baths}",
    #             pd.url,
    #             pd.listed.isoformat(),
    #         ],
    #         divider=False,
    #     )
    # return location_table.get_string()

    output_str = ""

    for pd in property_data_list:
        # check if items are known
        sqft = pd.sqft
        if sqft is None or sqft == 0:
            sqft = "???"

        beds = pd.beds
        if beds is None or beds == 0:
            beds = "?"

        baths = pd.baths
        if baths is None or baths == 0:
            baths = "?"

        # add row to table
        # location_table.add_row(
        #     [
        #         pd.price,
        #         f"{pd.street_address}, {pd.city}, {pd.state} {pd.zipcode}",
        #         sqft,
        #         f"{beds}/{baths}",
        #         pd.url,
        #         pd.listed.isoformat(),
        #     ],
        #     divider=False,
        # )

        output_str = f"{output_str} - {pd.street_address}, {pd.city}, {pd.state} {pd.zipcode}: {pd.price}\n   {beds} beds, {baths} baths, {sqft} sqft\n   {pd.url}\n\n"

    return output_str


def main(dry: bool) -> None:
    # load the config
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as fp:
            config_data = json.load(fp)
    else:
        config_data = json.loads(os.environ["CONFIG_DATA"])

    message_text = ""

    for location in config_data["LOCATIONS"]:
        location_text = f"{location['CITY']}, {location['STATE']}"

        print(f"Checking location: {location_text}")

        # build parameters
        body_query = {
            "sort": {"direction": "desc", "field": "list_date"},
            "city": location["CITY"],
            "limit": LIMIT,
            "offset": "0",
            "state_code": location["STATE"],
            "status": ["for_sale", "ready_to_build"],
        }

        # send request
        headers = {
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": config_data["RAPIDAPI_KEY"],
        }
        response = requests.post(URL, headers=headers, json=body_query)

        # parse response
        try:
            response_json = response.json()
        except requests.exceptions.JSONDecodeError:
            continue

        # # test info
        # with open("data.json", "r") as fp:
        #     response_json = json.load(fp)

        location_message = create_property_table(parse_property_list(response_json))
        message_text = f"{message_text}{''.join(['='*50])}\n\n{location_text}:\n\n{location_message}\n"

    print(message_text)

    if not dry:
        send_email(config_data, message_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Run without sending email")
    args = parser.parse_args()

    main(args.dry)
