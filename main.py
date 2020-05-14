import os
import smtplib, ssl
import requests
import datetime
import json
from email.message import EmailMessage

RAPIDAPI_HOST = "realtor.p.rapidapi.com"
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
URL = "https://realtor.p.rapidapi.com/properties/v2/list-for-sale"
LIMIT = 20

def now():
    return datetime.datetime.utcnow()

def main():
    message_text = "This is a test"

    locations = os.getenv("LOCATIONS").split(":")

    for location in locations:
        print(location)
        location_found = False
        message_text += "{}: \n".format(location)

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
        print(querystring)
        response = requests.request("GET", URL, headers=headers, params=querystring)
        data = response.json()

        # parse response
        for prop in data["properties"]:
            # test if last update time is sooner than one day ago
            last_update = datetime.datetime.strptime(prop["last_update"], '%Y-%m-%dT%H:%M:%SZ')
            if last_update > now() - datetime.timedelta(days=1):
                print("Property found that matches")
                location_found = True

                # get address
                address = prop["address"]
                pretty_address = "{}, {}, {} {}".format(address["line"], address["city"], address["state_code"], address["postal_code"])

                # other info
                pretty_url = prop["rdc_web_url"]
                pretty_price = "${:,}".format(prop["price"])

                message_text += " - {}: {}\n   {}\n".format(pretty_address, pretty_price, pretty_url)


        if not location_found:
            print("No listings found")
            # put nothing if no new listings
            message_text += "No new listings\n"

        # add line break between locations
        message_text += "\n"

    # send email
    print("Sending email to {}".format(os.getenv("DEST_EMAIL")))
    try:
        # prepare sever connection
        context = ssl.create_default_context()
        server = smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT")))
        server.starttls(context=context)
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))

        # build message
        message = EmailMessage()
        message.set_content(message_text)
        message["Subject"] = "Daily Realtor Update: {}".format(
            now().strftime("%Y-%m-%d")
        )
        message["From"] = "Daily Realtor <{}>".format(os.getenv("SMTP_FROM"))
        message["To"] = os.getenv("DEST_EMAIL")

        # send message
        server.send_message(message)

    except Exception as e:
        print("Unable to send email")
        print(e)

    finally:
        server.quit()

    print("Done!")


if __name__ == "__main__":
    main()
