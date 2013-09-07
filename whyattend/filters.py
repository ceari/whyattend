import datetime


def age(dt, now=None):
    if not now:
        now = datetime.datetime.utcnow()

    age = now - dt
    if age.days == 0:
        if age.seconds < 120:
            age_str = "a minute ago"
        elif age.seconds < 3600:
            age_str = "%d minutes ago" % (age.seconds / 60)
        elif age.seconds < 7200:
            age_str = "an hour ago"
        else:
            age_str = "%d hours ago" % (age.seconds / 3600)
    else:
        if age.days == 1:
            age_str = "yesterday"
        elif age.days <= 31:
            age_str = "%d days ago" % (age.days)
        elif age.days <= 72:
            age_str = "a month ago"
        elif age.days <= 365:
            age_str = "%d months ago" % (age.days / 30)
        elif age.days <= 2 * 365:
            age_str = "last year"
        else:
            age_str = "%d years ago" % (age.days / 365)

    return age_str