from datetime import datetime


def unix(date):
    return date.timestamp()

def deunix(unix):
    return datetime.fromtimestamp(unix)