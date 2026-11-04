from utils.settings import LOGIN_METHOD
from pydantic import BaseModel


if LOGIN_METHOD == "jfb":
    class LoginModel(BaseModel):
        user_name: str  
        password: str

    class LoginForceModel(BaseModel):
        user_name: str  
        password: str
        token: str

# elif LOGIN_METHOD == "jonathan":
#     login_parser.add_argument('user_name', type=str, required=False, location='json')
#     login_parser.add_argument('password', type=str, required=False, location='json')
#     login_parser.add_argument('Authorization', type=str, required=False, location='headers', help="Jonathan Token")
    
#     login_force_parser.add_argument('user_name', type=str, required=True, location='json')
#     login_force_parser.add_argument('password', type=str, required=False, location='json')
#     login_force_parser.add_argument('token', type=str, required=True, location='json')
#     login_parser.add_argument('Authorization', type=str, required=False, location='headers', help="Jonathan Token")
    
# elif LOGIN_METHOD == "kisti":
#     login_parser.add_argument('user_name', type=str, required=True, location='json')
#     login_parser.add_argument('password', type=str, required=True, location='json') 
#     login_parser.add_argument('otp', type=str, required=True, location='json')        
    
#     login_force_parser.add_argument('user_name', type=str, required=True, location='json')
#     login_force_parser.add_argument('password', type=str, required=True, location='json')
#     login_force_parser.add_argument('token', type=str, required=True, location='json')
