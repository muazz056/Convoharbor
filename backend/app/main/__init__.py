from flask import Blueprint

main = Blueprint('main', __name__)

# Import routes at the end to avoid circular dependencies
from . import routes