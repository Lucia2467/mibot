"""
wsgi.py - WSGI entry point for PythonAnywhere
This file is used by the PythonAnywhere web server to run the Flask app
"""

import sys
import os

# Add your project directory to the path
project_home = '/home/Isaax23/mibot'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = os.path.join(project_home, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Import the Flask app
from app import app as application

# Disable debug mode in production
application.debug = False
