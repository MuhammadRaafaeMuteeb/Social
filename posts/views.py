from django.conf import settings
import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from social_auth.models import SocialAccount
import logging
import json
from django.contrib import messages

#logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    # show connected accounts
    meta_accounts = SocialAccount.objects.filter(user=request.user, provider='meta')
    linkedin = SocialAccount.objects.filter(user=request.user, provider='linkedin').first()
    return render(request, "dashboard.html", {"meta_accounts": meta_accounts, "linkedin": linkedin})




@login_required
def new_post(request):
    if request.method == "POST":
        fb_response = post_to_facebook(request)

        try:
            data = json.loads(fb_response.content.decode("utf-8"))
        except Exception:
            data = {}

        if data.get("success"):
            # Pass success message to template instead of redirecting
            return render(
                request,
                "posts/new_post.html",
                {
                    "success": "Post published to Facebook successfully!",
                    "error": None
                }
            )
        else:
            # Pass error message to template
            error_msg = data.get("error") or "Unknown error"
            print("Facebook API error:", data)
            return render(
                request,
                "posts/new_post.html",
                {
                    "error": error_msg,
                    "success": None
                }
            )

    # GET request
    return render(request, "posts/new_post.html")

@csrf_exempt
@login_required
def post_to_facebook(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=400)

    message = request.POST.get("message") or request.POST.get("text")
    image_url = request.POST.get("image_url")

    # Get the user's connected FB account
    fb = SocialAccount.objects.filter(
        user=request.user,
        provider='meta',
        extra__kind='facebook'
    ).first()
    if not fb:
        return JsonResponse({"success": False, "error": "No connected Facebook account"}, status=400)

    # Get pages for user
    pages = requests.get(
        "https://graph.facebook.com/v17.0/me/accounts",
        params={
            "access_token": fb.access_token,
            "fields": "id,name,access_token"
        },
        timeout=10
    ).json()

    if 'data' not in pages or not pages['data']:
        return JsonResponse({"success": False, "error": "No pages found for this FB user", "raw": pages}, status=400)

    page = pages['data'][0]
    page_token = page.get('access_token')
    page_id = page.get('id')

    # Post to Facebook
    if image_url:
        resp = requests.post(
            f"https://graph.facebook.com/v17.0/{page_id}/photos",
            data={
                "url": image_url,
                "caption": message,
                "access_token": page_token
            },
            timeout=10
        ).json()
    else:
        resp = requests.post(
            f"https://graph.facebook.com/v17.0/{page_id}/feed",
            data={
                "message": message,
                "access_token": page_token
            },
            timeout=10
        ).json()

    fb_id = resp.get("id") or resp.get("post_id") or resp.get("facebook_post_id")
    if fb_id:
        return JsonResponse({"success": True, "id": fb_id})
    else:
        return JsonResponse({"success": False, "error": resp.get("error", "Unknown error"), "raw": resp})


@csrf_exempt
@login_required
def post_to_instagram(request):
    if request.method != "POST":
        return JsonResponse({"error":"POST required"}, status=400)
    caption = request.POST.get("caption") or request.POST.get("message")
    image_url = request.POST.get("image_url")
    ig = SocialAccount.objects.filter(user=request.user, provider='meta', extra__kind='instagram').first()
    if not ig:
        return JsonResponse({"error":"No connected Instagram account"}, status=400)
    # Need page token for publishing (use associated page's access token)
    # Find a page that has this instagram_business_account
    pages = requests.get("https://graph.facebook.com/v17.0/me/accounts", params={"access_token": ig.access_token, "fields":"id,name,instagram_business_account,access_token"}, timeout=10).json()
    # find page with ig id matching ig.account_id
    page_token = None
    page_id = None
    for p in pages.get("data",[]):
        insta = p.get("instagram_business_account")
        if insta and insta.get("id") == ig.account_id:
            page_id = p.get("id")
            page_token = p.get("access_token")
            break
    if not page_token:
        # fallback: try first page
        if pages.get("data"):
            page_id = pages["data"][0].get("id")
            page_token = pages["data"][0].get("access_token")
    if not page_token:
        return JsonResponse({"error":"No page token available for IG publishing","raw":pages}, status=400)
    if not image_url:
        return JsonResponse({"error":"image_url required for IG publish"}, status=400)
    # create media object
    create = requests.post(f"https://graph.facebook.com/v17.0/{ig.account_id}/media", data={"image_url":image_url,"caption":caption,"access_token":page_token}, timeout=10).json()
    creation_id = create.get("id")
    if not creation_id:
        return JsonResponse({"error":"Failed create media","raw":create}, status=400)
    publish = requests.post(f"https://graph.facebook.com/v17.0/{ig.account_id}/media_publish", data={"creation_id":creation_id,"access_token":page_token}, timeout=10).json()
    return JsonResponse(publish)

@csrf_exempt
@login_required
def post_to_linkedin(request, text):
    token = settings.LINKEDIN_ACCESS_TOKEN  # your hardcoded token in settings.py
    text = request.POST.get("text", "")

    if not token:
        return JsonResponse({"error": "No LinkedIn token found in settings"})

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    payload = {
        "author": settings.LINKEDIN_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }

    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json=payload
    )

    return JsonResponse(resp.json())