from django.shortcuts import render, redirect
from django.http import StreamingHttpResponse
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import MotionAlert
from .forms import SignupForm
import cv2
import time
from datetime import datetime
import base64
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from twilio.rest import Client
import telegram
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse

# Constants for distance calculation
KNOWN_WIDTH = 0.2  # Known width of the object in meters (example: 20 cm)
FOCAL_LENGTH = 615  # Focal length of the camera (adjust based on your camera)

# Threshold for significant change in width
SIGNIFICANT_CHANGE_THRESHOLD = 0.05  # 5 cm change
MOTION_STD_THRESHOLD = 5000  # Adjust this threshold based on your testing

# Email settings
SMTP_SERVER = 'smtp.office365.com'
SMTP_PORT = 587
SMTP_USERNAME = 'ptlyash24@gmail.com'
SMTP_PASSWORD = 'pttefaawsgcmqjca'
EMAIL_SENDER = 'ptlyash24@gmail.com'
EMAIL_RECIPIENT = 'yash.pankesh@gmail.com'

# Twilio SMS settings
TWILIO_ACCOUNT_SID = 'AC15fdf4f1e6e1d343f1d271f90b5d822e'  # Replace with your Twilio Account SID
TWILIO_AUTH_TOKEN = 'f5cc3280df16b30c0a93aa74a0df5ce3'  # Replace with your Twilio Auth Token
TWILIO_PHONE_NUMBER = '+12707516868'  # Replace with your Twilio phone number
RECIPIENT_PHONE_NUMBER = '+916358056783'  # Replace with the recipient's phone number


TELEGRAM_BOT_TOKEN = '7291344095:AAHmsY6pRJByQKVqlsCkZGYFue4OpIo43z8'  # Replace with your Telegram bot token
TELEGRAM_CHAT_ID = '6241199976'  # Replace with your Telegram chat ID

def detect_motion(frame1, frame2):
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)
    gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)
    frame_delta = cv2.absdiff(gray1, gray2)
    thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_areas = [cv2.contourArea(c) for c in contours]
    motion_std = np.std(contour_areas) if contour_areas else 0
    motion_detected = motion_std > MOTION_STD_THRESHOLD
    return motion_detected, contours, motion_std

def calculate_distance(known_width, focal_length, perceived_width):
    if perceived_width == 0:
        return None
    return (known_width * focal_length) / perceived_width

def send_alert(alert_time, distance, image_data):
    message_body = f"Alert! Motion detected at {alert_time}. Distance to object: {distance:.2f} meters."
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=RECIPIENT_PHONE_NUMBER
        )
        print(f"Alert SMS sent to {RECIPIENT_PHONE_NUMBER}. Message SID: {message.sid}")
    except Exception as e:
        print(f"Failed to send SMS alert: {e}")
    
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECIPIENT
        msg['Subject'] = 'Motion Detection Alert'
        msg.attach(MIMEText(message_body, 'plain'))
        image = MIMEImage(image_data)
        image.add_header('Content-Disposition', 'attachment; filename="motion_detected.jpg"')
        msg.attach(image)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        print(f"Alert email sent to {EMAIL_RECIPIENT}.")
    except Exception as e:
        print(f"Failed to send email alert: {e}")
    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_body)
        bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=image_data)
        print("Alert sent to Telegram.")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.set_debuglevel(1)  # Enable debug logs
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
            print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


def motion_detection_view(request):
    return render(request, 'home.html')

def gen(camera):
    time.sleep(2)  # Warm up the camera
    last_frame = None
    alert_issued = False
    alert_interval = 10  # seconds
    last_alert_time = 0
    frame_rate = 60  # frames per second
    prev_time = 0
    last_width = 0

    while True:
        ret, frame = camera.read()
        if not ret:
            break
        frame = cv2.resize(frame, (640, 480))
        current_time = time.time()
        if current_time - prev_time > 1.0 / frame_rate:
            prev_time = current_time
            if last_frame is None:
                last_frame = frame
                continue
            motion_detected, contours, motion_std = detect_motion(last_frame, frame)
            if motion_detected and (current_time - last_alert_time > alert_interval):
                alert_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _, jpeg_image = cv2.imencode('.jpg', frame)
                image_data = jpeg_image.tobytes()
                print(f"Motion detected at {alert_time}! Alert issued. Motion STD: {motion_std:.2f}")
                for contour in contours:
                    if cv2.contourArea(contour) > 10000:
                        (x, y, w, h) = cv2.boundingRect(contour)
                        distance = calculate_distance(KNOWN_WIDTH, FOCAL_LENGTH, w)
                        if distance is not None and 0 <= distance <= 3:
                            if last_width == 0 or abs(w - last_width) > SIGNIFICANT_CHANGE_THRESHOLD * FOCAL_LENGTH / distance:
                                cv2.line(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                                cv2.putText(frame, f"Distance: {distance:.2f}m", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                send_alert(alert_time, distance, image_data)
                                MotionAlert.objects.create(image=image_data, distance=distance)
                                last_alert_time = current_time
                                last_width = w
                                break  # Only send one notification per alert
            last_frame = frame
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame = jpeg.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

def video_feed(request):
    url = 'http://192.168.43.228:8080/video'  # Replace with your URL
    cap = cv2.VideoCapture(url)
    return StreamingHttpResponse(gen(cap), content_type="multipart/x-mixed-replace;boundary=frame")
    

def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log the user in after signup
            return redirect(reverse('index')) # Redirect to the home page
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect(reverse('index'))
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

@csrf_protect
def custom_logout(request):
    if request.method == 'POST':
        logout(request)
        return redirect(reverse('login'))
    return render(request, 'login.html')

@login_required
def home(request):
    alerts = MotionAlert.objects.all()
    for alert in alerts:
        alert.image = base64.b64encode(alert.image).decode('utf-8')
    return render(request, 'home.html', {'alerts': alerts})
   

@login_required
def index(request):
    return render(request, 'index.html')

@login_required
def object_detection(request):
    return render(request, 'object_detection.html')

@login_required
def display_images(request):
    alerts = MotionAlert.objects.all()
    for alert in alerts:
        alert.image = base64.b64encode(alert.image).decode('utf-8')
    return render(request, 'display_images.html', {'alerts': alerts})


                                    