import datetime
import os
import smtplib
import ssl
from email.message import EmailMessage

import requests

RAPIDAPI_HOST = "realtor.p.rapidapi.com"
RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
URL = f"https://{RAPIDAPI_HOST}/properties/v2/list-for-sale"
LIMIT = 20


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def send_email(message_text: str):
    # send email
    print(f'Sending email to {os.environ["DEST_EMAIL"]}')
    print(f"Message:\n {message_text}")

    server = smtplib.SMTP(os.environ["SMTP_SERVER"], int(os.environ["SMTP_PORT"]))

    try:
        # prepare sever connection
        context = ssl.create_default_context()
        server.starttls(context=context)
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])

        # build message
        message = EmailMessage()
        message.set_content(message_text)
        message["Subject"] = f'Daily Realtor Update: {now().strftime("%Y-%m-%d")}'
        message["From"] = f'Daily Realtor <{os.environ["SMTP_FROM"]}>'
        message["To"] = os.environ["DEST_EMAIL"]

        # send message
        server.send_message(message)

    except Exception as e:
        print("Unable to send email")
        print(e)
    finally:
        server.quit()


def main():
    message_text = ""

    # locations is expected to be a list of City,State seperated by semicolons
    locations = os.environ["LOCATIONS"].split(":")

    for location in locations:
        print(f"Checking location: {location}")
        location_found = False
        message_text += f"{location}: \n"

        # get location info
        (city, state) = location.split(",")

        # build parameters
        querystring = {
            "sort": "newest",
            "city": city,
            "limit": LIMIT,
            "offset": "0",
            "state_code": state,
        }

        # send request
        headers = {"x-rapidapi-host": RAPIDAPI_HOST, "x-rapidapi-key": RAPIDAPI_KEY}
        response = requests.request("GET", URL, headers=headers, params=querystring)

        # parse response
        data = response.json()
        print(f"{len(data['properties'])} properties found")

        for prop in data["properties"]:
            # test if last update time is sooner than one day ago
            try:
                last_update = datetime.datetime.strptime(
                    prop["last_update"], "%Y-%m-%dT%H:%M:%SZ"
                )
            except ValueError:
                last_update = datetime.datetime.strptime(
                    prop["last_update"], "%Y-%m-%d"
                )

            if last_update > now() - datetime.timedelta(days=1):
                location_found = True

                # get address
                address = prop["address"]
                pretty_address = f'{address["line"]}, {address["city"]}, {address["state_code"]} {address["postal_code"]}'

                # other info
                pretty_url = prop["rdc_web_url"]
                pretty_price = "${:,}".format(prop["price"])

                message_text += (
                    f" - {pretty_address}: {pretty_price}\n   {pretty_url}\n"
                )

        if not location_found:
            # put nothing if no new listings
            message_text += "No new listings\n"

        # add line break between locations
        message_text += "\n"

    send_email(message_text)


if __name__ == "__main__":
    main()
