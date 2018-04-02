from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import wraps
from django.db import transaction


class LoginRequiredMixin(object):
    """验证用户的登录状态"""
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)


def login_required_json(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated():
            # 如果用户未登录，返回json数据
            return JsonResponse({"code": 1, "message": "用户未登录"})
        else:
            # 如果用户登录，则进入到视图函数中执行
            return view_func(request, *args, **kwargs)
    return wrapper


class LoginRequiredJsonMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredJsonMixin, cls).as_view(**initkwargs)
        return login_required_json(view)


class TransactionAtomicMixin(object):
    """提供数据库事务功能"""
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(TransactionAtomicMixin, cls).as_view(**initkwargs)
        return transaction.atomic(view)





