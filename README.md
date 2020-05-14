# Daily Realtor

This is a script for my mom to send her new Realtor.com
listings in nearby locations every day.

## Setup
First, you'll need to install [Requests](https://requests.readthedocs.io/en/master/).

Next, you're going to need a lot of environment variables. See [run.example.py](/blob/master/run.example.py)

```bash
RAPIDAPI_KEY # rapidapi.com API key: https://rapidapi.com/apidojo/api/realtor

LOCATIONS # a colon-separated list of city and state codes (those separated by a comma)
DEST_EMAIL # destination email address

SMTP_SERVER # email server
SMTP_PORT # email server port
SMTP_FROM # from email address
SMTP_USER # email server username
SMTP_PASS # email server password
```