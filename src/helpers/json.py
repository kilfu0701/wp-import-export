from datetime import date, datetime

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        #return obj.isoformat()
        try:
            return obj.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        except:
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    raise TypeError("Type %s not serializable" % type(obj))
