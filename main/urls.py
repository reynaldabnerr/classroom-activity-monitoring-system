from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    path('redirect/', views.role_redirect, name='role-redirect'),

    path('guru/dashboard/', views.teacher_dashboard, name='teacher-dashboard'),
    path('guru/upload/', views.upload_video, name='teacher-upload'),
    path('guru/submission/<int:submission_id>/', views.teacher_submission_detail, name='teacher-submission-detail'),
    path('guru/submission/<int:submission_id>/delete/', views.delete_submission, name='teacher-delete-submission'),
    path('guru/processing/<int:submission_id>/', views.teacher_processing, name='teacher-processing'),
    path('guru/api/submission/<int:submission_id>/status/', views.submission_processing_status, name='submission-status'),

    path('kepala-sekolah/dashboard/', views.principal_dashboard, name='principal-dashboard'),
    path('kepala-sekolah/submission/<int:submission_id>/', views.principal_submission_detail, name='principal-submission-detail'),

    path('about/', views.about, name='about'),
]
