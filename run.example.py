import os

os.environ["RAPIDAPI_KEY"] = "apikeygoeshere"

os.environ["LOCATIONS"] = "Austin,TX:Dallas,TX:Des Moines,IA"
os.environ["DEST_EMAIL"] = "me@myemail.com"

os.environ["SMTP_SERVER"] = "smtp.sendgrid.net"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_FROM"] = "daily-realtor@mydomain.com"
os.environ["SMTP_USER"] = "apikey"
os.environ["SMTP_PASS"] = "apikeygoeshere"

import main
main.main()