"""
认证工具模块
提供统一的登录验证装饰器和安全相关工具函数
"""
from functools import wraps
from flask import session, jsonify, redirect, url_for, request


def login_required(f):
    """
    登录验证装饰器
    
    用于保护需要登录才能访问的路由。
    对于 API 请求（Accept: application/json 或 XHR）返回 JSON 错误，
    对于页面请求则重定向到登录页面。
    
    使用方式:
        @app.route('/protected')
        @login_required
        def protected_route():
            return "This is protected"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # 判断是否为 API 请求
            is_api_request = (
                request.headers.get('Accept', '').startswith('application/json') or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                request.path.startswith('/api/')
            )
            
            if is_api_request:
                return jsonify({
                    "status": "error",
                    "message": "请先登录",
                    "code": "UNAUTHORIZED"
                }), 401
            else:
                return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user_id():
    """获取当前登录用户的 ID"""
    return session.get('user_id')


def get_current_username():
    """获取当前登录用户的用户名"""
    return session.get('username')
