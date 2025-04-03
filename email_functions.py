from secret_info import *



import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# SMTP Ayarları
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = my_email
EMAIL_PASSWORD = my_password



def send_token_to_email(email_reciever, token,web_site_url = web_site_url):

    # Mail içeriği
    subject = "Hesabınızı Onaylayın"
    body = f"""
    Merhaba,

    Hesabınızı onaylamak için aşağıdaki linke tıklayın:

    http://{web_site_url}/confirm_email/{token}

    Eğer bu isteği siz yapmadıysanız, bu maili göz ardı edebilirsiniz.

    İyi günler!
    """

    # Mail formatı (HTML ve Plain)
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = email_reciever
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # SMTP Bağlantısı Kur ve Mail Gönder
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls(context=context)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email_reciever, msg.as_string())
        server.quit()
        print("Mail başarıyla gönderildi!")
    except Exception as e:
        print("Hata oluştu:", e)
        

