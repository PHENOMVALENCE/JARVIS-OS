from etext import send_sms_via_email

phone_number = "4632099000"
message = "hello world!"
provider = "T-Mobile"

sender_credentials = ("email@gmail.com", "email_password")

send_sms_via_email(
    phone_number, message, provider, sender_credentials, subject=""
)
