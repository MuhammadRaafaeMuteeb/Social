from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages

def signup(request):
    if request.method=='POST':
        username = request.POST.get('username')
        pwd = request.POST.get('password')
        if User.objects.filter(username=username).exists():
            messages.error(request,'User exists')
        else:
            user = User.objects.create_user(username=username, password=pwd)
            login(request, user)
            return redirect('/dashboard/')
    return render(request,'accounts/signup.html')

def login_view(request):
    if request.method=='POST':
        username=request.POST.get('username'); pwd=request.POST.get('password')
        user = authenticate(request, username=username, password=pwd)
        if user:
            login(request,user); return redirect('/dashboard/')
        else:
            messages.error(request,'Invalid credentials')
    return render(request,'accounts/login.html')

def logout_view(request):
    logout(request); return redirect('/accounts/login/')
