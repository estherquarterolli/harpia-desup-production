#!/usr/bin/env python
"""
Script to verify Supabase and deployment configuration.

Run this before deploying to ensure everything is configured correctly.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from django.conf import settings
from decouple import config


def main():
    """Run configuration checks."""
    print("\n" + "=" * 60)
    print(" Supabase & Deployment Configuration Checker ".center(60))
    print("=" * 60 + "\n")

    issues = []

    # Check database
    print("[1] Testing Database Connection...")
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("    [OK] Database connected successfully\n")
    except Exception as e:
        print(f"    [FAIL] Database error: {e}\n")
        issues.append(f"Database: {e}")

    # Check migrations
    print("[2] Checking Django Migrations...")
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('migrate', '--plan', stdout=out)
        print("    [OK] Migrations checked successfully\n")
    except Exception as e:
        print(f"    [WARN] Migration issue: {e}\n")

    # Check Supabase variables
    print("[3] Checking Supabase Configuration...")
    supabase_url = config("SUPABASE_URL", default="")
    supabase_key = config("SUPABASE_KEY", default="")
    if supabase_url and supabase_key:
        print(f"    [OK] SUPABASE_URL: {supabase_url[:20]}...")
        print(f"    [OK] SUPABASE_KEY: {supabase_key[:20]}...\n")
    else:
        print("    [INFO] Supabase not configured (local development)\n")

    # Check SECRET_KEY
    print("[4] Checking SECRET_KEY...")
    secret = settings.SECRET_KEY
    if secret.startswith('django-insecure'):
        print("    [WARN] Using insecure SECRET_KEY\n")
        issues.append("Generate new SECRET_KEY for production")
    else:
        print("    [OK] SECRET_KEY is set\n")

    # Check DEBUG
    print("[5] Checking DEBUG setting...")
    if settings.DEBUG:
        print("    [INFO] DEBUG=True (OK for development)\n")
    else:
        print("    [OK] DEBUG=False (production mode)\n")

    # Check ALLOWED_HOSTS
    print("[6] Checking ALLOWED_HOSTS...")
    print(f"    ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}\n")

    # Summary
    print("=" * 60)
    if issues:
        print(f"\n[WARNINGS] {len(issues)} item(s) to check:\n")
        for item in issues:
            print(f"   - {item}")
    else:
        print("\n[OK] All checks passed!")

    print("\n" + "=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
