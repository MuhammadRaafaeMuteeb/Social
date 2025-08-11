
import requests
import urllib.parse
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from .models import SocialAccount
from django.http import JsonResponse
from django.contrib import messages

# ---------------- CONNECT VIEWS ----------------

@login_required
def connect_facebook(request):
    fb_auth_url = "https://www.facebook.com/v17.0/dialog/oauth"
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "scope": "pages_manage_posts,pages_read_engagement,pages_show_list",
        "response_type": "code"
    }
    return redirect(f"{fb_auth_url}?{urllib.parse.urlencode(params)}")

@login_required
def connect_instagram(request):
    ig_auth_url = "https://www.facebook.com/v17.0/dialog/oauth"
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.INSTAGRAM_REDIRECT_URI,
        "scope": "instagram_basic,instagram_content_publish,pages_show_list",
        "response_type": "code"
    }
    return redirect(f"{ig_auth_url}?{urllib.parse.urlencode(params)}")

@login_required
def connect_linkedin(request):
    linkedin_auth_url = "https://www.linkedin.com/oauth/v2/authorization"
    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "scope": "w_member_social offline_access"
    }
    return redirect(f"{linkedin_auth_url}?{urllib.parse.urlencode(params)}")

# ---------------- CALLBACK VIEWS ----------------

@login_required
def facebook_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect('dashboard')

    token_resp = requests.get(
        'https://graph.facebook.com/v17.0/oauth/access_token',
        params={
            'client_id': settings.META_APP_ID,
            'redirect_uri': settings.FACEBOOK_REDIRECT_URI,
            'client_secret': settings.META_APP_SECRET,
            'code': code
        },
        timeout=10
    ).json()
    short_token = token_resp.get('access_token')
    if not short_token:
        return redirect('dashboard')

    long_token_resp = requests.get(
        'https://graph.facebook.com/v17.0/oauth/access_token',
        params={
            'grant_type': 'fb_exchange_token',
            'client_id': settings.META_APP_ID,
            'client_secret': settings.META_APP_SECRET,
            'fb_exchange_token': short_token
        },
        timeout=10
    ).json()
    long_token = long_token_resp.get('access_token', short_token)

    user_info = requests.get(
        'https://graph.facebook.com/me',
        params={'fields': 'id,name', 'access_token': long_token},
        timeout=10
    ).json()

    # store as provider 'meta' with extra.kind = 'facebook'
    sa, _ = SocialAccount.objects.update_or_create(
        user=request.user,
        provider='meta',
        account_id=user_info.get('id'),
        defaults={'access_token': long_token, 'extra': {'kind': 'facebook', 'name': user_info.get('name')}}
    )
    return redirect('dashboard')

@login_required
def instagram_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect('dashboard')

    token_resp = requests.get(
        'https://graph.facebook.com/v17.0/oauth/access_token',
        params={
            'client_id': settings.META_APP_ID,
            'redirect_uri': settings.INSTAGRAM_REDIRECT_URI,
            'client_secret': settings.META_APP_SECRET,
            'code': code
        },
        timeout=10
    ).json()
    short_token = token_resp.get('access_token')
    if not short_token:
        return redirect('dashboard')

    long_token_resp = requests.get(
        'https://graph.facebook.com/v17.0/oauth/access_token',
        params={
            'grant_type': 'fb_exchange_token',
            'client_id': settings.META_APP_ID,
            'client_secret': settings.META_APP_SECRET,
            'fb_exchange_token': short_token
        },
        timeout=10
    ).json()
    long_token = long_token_resp.get('access_token', short_token)

    # find IG business account id via pages
    me_info = requests.get(
        'https://graph.facebook.com/v17.0/me/accounts',
        params={'access_token': long_token, 'fields': 'id,name,instagram_business_account'},
        timeout=10
    ).json()

    ig_id = None
    ig_name = None
    if 'data' in me_info:
        for p in me_info['data']:
            ig = p.get('instagram_business_account')
            if ig and ig.get('id'):
                ig_id = ig.get('id')
                ig_name = p.get('name') or 'Instagram'
                break

    SocialAccount.objects.update_or_create(
        user=request.user,
        provider='meta',
        account_id=ig_id or f"ig_unknown_{request.user.id}",
        defaults={'access_token': long_token, 'extra': {'kind': 'instagram', 'name': ig_name or 'Instagram Account'}}
    )
    return redirect('dashboard')

def linkedin_callback(request):
    code = request.GET.get("code")
    if not code:
        messages.error(request, "Missing authorization code.")
        return redirect("/")

    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
    }
    resp = requests.post(token_url, data=data)
    token_json = resp.json()

    if "access_token" not in token_json:
        messages.error(request, f"LinkedIn token error: {token_json}")
        return redirect("/")

    access_token = token_json["access_token"]

    # Store access_token in DB for the logged-in user
    request.user.socialtoken_set.update_or_create(
        provider="linkedin",
        defaults={"token": access_token}
    )

    messages.success(request, "LinkedIn connected successfully!")
    return redirect("/")