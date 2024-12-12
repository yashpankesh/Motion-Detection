from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from .views import custom_logout

urlpatterns = [
    path('', views.index, name='index'),
    path('home/', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.custom_logout , name='logout'),
    path('video_feed/', views.video_feed, name='video-feed'),
    path('object_detection/', views.object_detection, name='object_detection'),
    path('display_images/', views.display_images, name='display_images'),
]
