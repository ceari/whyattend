"""
    Development server.
    DO NOT use this for application deployment.
"""

from whyattend.webapp import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
