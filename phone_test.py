import smtplib
from email.message import EmailMessage

def email_alert(subject, body, to):
    msg = EmailMessage()
    msg.set_content(body)
    msg['subject'] = subject
    msg['to'] = to

    user = "colehacker381@gmail.com"
    msg['from'] = user
    password = "flwi dfui dbxd pwho"
    
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(user, password)
    server.send_message(msg)
    server.quit()

katie_stout = "3173844858@vtext.com"
allen_stout = "3172131333@vtext.com"
ellie = "3179198020@vtext.com"
cole = "4632099000@vtext.com"
grampy = "3177142579@vtext.com"


if __name__ == '__main__':
    email_alert("", "reminder", cole)
    