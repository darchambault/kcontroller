from functools import wraps
from flask import Blueprint, Response
import jsonpickle
from werkzeug.wrappers import BaseResponse


dashboard = Blueprint('dashboard', __name__, static_folder='../static/dashboard')
controller = None


def to_json(api_call):
    def encode(data):
        return jsonpickle.encode(data, unpicklable=False)

    @wraps(api_call)
    def decorator(*args, **kwargs):
        try:
            result = api_call(*args, **kwargs)
            return result if isinstance(result, BaseResponse) else Response(encode(result), 200, {'Content-Type': 'application/json'})
        except Exception as e:
            return Response(e.message, 500)
    return decorator


@dashboard.route('/', methods=['GET'])
def get_base():
    return dashboard.send_static_file('dashboard.html')
