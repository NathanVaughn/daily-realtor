import argparse
import datetime
import json
import math
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

import pydantic
import requests


class SMTPConfig(pydantic.BaseModel):
    SERVER: str
    PORT: int
    USER: str
    PASS: str
    FROM_EMAIL: str


class Config(pydantic.BaseModel):
    RAPIDAPI_KEY: str
    ZIP_CODES: list[str]
    DESTINATION_EMAIL: str
    SMTP: SMTPConfig


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


# https://rapidapi.com/apidojo/api/realty-in-us/playground/apiendpoint_c4d477ea-7292-48fa-9dfe-f093f2adf8ac

RAPIDAPI_HOST = "realty-in-us.p.rapidapi.com"
URL = f"https://{RAPIDAPI_HOST}/properties/v3/list"
LIMIT = 20  # items per response

# current time
NOW = datetime.datetime.now()

# load the config
_config_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), "config.json")
if os.path.isfile(_config_file):
    with open(_config_file, "r") as fp:
        _config_data = json.load(fp)
else:
    _config_data = json.loads(os.environ["CONFIG_DATA"])

CONFIG = Config(**_config_data)


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


def send_email(message_text: str) -> None:
    """
    Send an email with the given message
    """

    print("Sending email")

    server = smtplib.SMTP(CONFIG.SMTP.SERVER, CONFIG.SMTP.PORT)

    try:
        # prepare sever connection
        context = ssl.create_default_context()
        server.starttls(context=context)
        server.login(CONFIG.SMTP.USER, CONFIG.SMTP.PASS)

        # build message
        message = EmailMessage()
        message.set_content(message_text)
        message["Subject"] = f'Daily Realtor Update: {NOW.strftime("%Y-%m-%d")}'
        message["From"] = f"Daily Realtor <{CONFIG.SMTP.FROM_EMAIL}>"
        message["To"] = CONFIG.DESTINATION_EMAIL

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
    message_text = ""

    for zip_code in CONFIG.ZIP_CODES:
        print(f"Checking zip code: {zip_code}")

        # build parameters
        body_query = {
            "sort": {"direction": "desc", "field": "list_date"},
            "postal_code": zip_code,
            "limit": LIMIT,  # items per response
            "offset": "0",
            "status": ["for_sale", "ready_to_build"],
        }

        # send request
        headers = {
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": CONFIG.RAPIDAPI_KEY,
        }
        response = requests.post(URL, headers=headers, json=body_query)

        # parse response
        try:
            response_json = response.json()
        except requests.exceptions.JSONDecodeError as e:
            print(f"Error decoding JSON response, skipping: {e}")
            continue

        # test info
        # with open("response.json", "w") as fp:
        #     json.dump(response_json, fp, indent=4)

        location_message = create_property_table(parse_property_list(response_json))
        message_text = f"{message_text}{''.join(['='*50])}\n\nZip Code {zip_code}:\n\n{location_message}\n"

    print(message_text)

    if not dry:
        send_email(message_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Run without sending email")
    args = parser.parse_args()

    main(args.dry)
