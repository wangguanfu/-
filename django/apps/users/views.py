from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.generic import View
from django.core.urlresolvers import reverse
import re
from users.models import User, Address
from django import db
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_active_email
from django.contrib.auth import authenticate, login, logout
from utils.views import LoginRequiredMixin
from django_redis import get_redis_connection
from goods.models import GoodsSKU
import json

# Create your views here.

#
# def register(request):
#     """用户注册"""
#     # 用户的请求方式
#     if request.method == "GET":
#         # 处理get请求方式，提供页面
#         return render(request, "register.html")
#     else:
#         # 处理post请求方式，处理注册数据
#         return HttpResponse("这是post请求返回的页面")


class RegisterView(View):
    """用户注册"""
    def get(self, request):
        """处理get请求, 提供注册页面"""
        return render(request, "register.html")

    def post(self, request):
        """处理post请求，处理注册数据"""
        # 获取前端发送的数据/参数
        user_name = request.POST.get("user_name")
        password = request.POST.get("pwd")
        email = request.POST.get("email")
        allow = request.POST.get("allow")

        # 参数校验
        if not all([user_name, password, email]):
            # 如果参数不完整，从定向到注册页面
            return redirect(reverse("users:register"))

        if not re.match(r"^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$", email):
            # 如果email格式不正确
            return render(request, "register.html", {"errmsg": "邮箱格式不正确！"})

        if allow != "on":
            # 如果用户没有勾选协议
            return render(request, "register.html", {"errmsg": "请同意协议！"})

        # 进行业务逻辑处理
        # 将密码加密
        # 将用户数据保存到数据库中
        # user = User()
        # user.save()

        # 使用django的认证系统创建用户
        try:
            user = User.objects.create_user(user_name, email, password)
        except db.IntegrityError:
            # 如果抛出此异常，表示用户已经注册
            return render(request, "register.html", {"errmsg": "用户已注册！"})

        # 将用户的激活状态设置为假
        user.is_active = False
        user.save()

        # 生成激活token
        token = user.generate_active_token()

        # 使用celery发送邮件
        send_active_email.delay(email, user_name, token)

        # 返回给前端结果
        return redirect(reverse("goods:index"))


class ActiveView(View):
    """激活"""
    def get(self, request, token):
        # 根据token 解析，获取用户的id
        # 创建转换工具（序列化器)
        s = Serializer(settings.SECRET_KEY, 3600)
        # 解析
        try:
            ret = s.loads(token)
        except SignatureExpired:
            # 如果出现异常，表示token过期，返回信息给用户
            return HttpResponse("激活链接已过期")

        # 更新用户在数据库中的激活状态
        user_id = ret.get("confirm")
        # 查询数据库
        try:
		
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            # 用户不存在
            return HttpResponse("用户不存在")

        user.is_active = True
        user.save()

        # 返回信息给用户
        return redirect(reverse("users:login"))


class LoginView(View):
    """登录"""
    def get(self, request):
        """提供登录页面"""
        return render(request, "login.html")

    def post(self, request):
        """处理登录请求"""
        user_name = request.POST.get("username")
        password = request.POST.get("pwd")
        remembered = request.POST.get("remembered")

        if not all([user_name, password]):
            return redirect(reverse("users:login"))

        #
        # password = sha256(password)
        # User.objects.get(username=user_name, password=password)

        # 使用django的认证系统
        user = authenticate(username=user_name, password=password)
        if user is None:
            # 表示用户的认证失败
            return render(request, "login.html", {"errmsg": "用户名或密码错误"})

        # 表示用户认证成功
        # 判断用户的激活状态
        if user.is_active is False:
            # 表示用户未激活
            return render(request, "login.html", {"errmsg": "用户名尚未激活"})

        # 在session中保存用户的登录状态信息
        login(request, user)

        # 处理记住用户名的逻辑
        if remembered != "on":
            # 不需要记住用户状态
            # 使用set_expiry设置 session 有效期
            request.session.set_expiry(0)
        else:
            # 需要记住用户状态
            request.session.set_expiry(None)

        # 将cookie中的购物车数据与redis中的购物车数据合并
        # 从cookie中获取购物车数据
        cart_json = request.COOKIES.get("cart")
        if cart_json is not None:
            cart_cookie = json.loads(cart_json)
        else:
            cart_cookie = {}

        # 从redis中获取购物车数据
        redis_conn = get_redis_connection("default")
        cart_redis = redis_conn.hgetall("cart_%s" % user.id)

        # 进行合并
        # cart_redis.update(cart_cookie)
        for sku_id, count in cart_cookie.items():
            # 在redis中的键与值都是bytes类型, 在cookie中的sku_id是str类型
            sku_id = sku_id.encode()  # 将str类型的sku_id转为bytes类型
            if sku_id in cart_redis:  # {b'1': b'3'}
                # cookie中有的商品，在redis中也有，进行数量求和，再设置到redis对应的购物车中
                origin_count = cart_redis[sku_id]
                count += int(origin_count)

            cart_redis[sku_id] = count

        # 将合并的购物车数据保存到redis中
        if cart_redis:
            redis_conn.hmset("cart_%s" % user.id, cart_redis)

        # 清除cookie中的购物车数据
        # 登录成功，根据next参数跳转页面
        next = request.GET.get("next")
        if next is None:
            # 如果没有next参数，跳转到主页
            response = redirect(reverse("goods:index"))
        else:
            # 如果next存在，跳转到next路径
            response = redirect(next)

        response.delete_cookie("cart")
        return response


class LogoutView(View):
    """退出"""
    def get(self, request):
        """"""
        # 将用户的session数据删除 ,使用logout将用户的session数据删除
        logout(request)
        return redirect(reverse("goods:index"))


class AddressView(LoginRequiredMixin, View):
    """用户地址"""
    def get(self, request):
        # 获取登录的用户
        user = request.user

        # 获取地址信息
        #
        # Address.objects.filter(user=user).order_by("create_time")[0]
        #
        # user.address_set.order_by("create_time")[0]
        #
        try:
            address = user.address_set.latest("create_time")
        except Address.DoesNotExist:
            # 如果地址信息不存在
            address = None

        context = {
            # "user": user,  # django的模板中可以直接使用user模板变量
            "address": address
        }

        return render(request, "user_center_site.html", context)

    def post(self, request):
        """修改地址信息"""
        user = request.user
        recv_name = request.POST.get("recv_name")
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        recv_mobile = request.POST.get("recv_mobile")

        if all([recv_name, addr, zip_code, recv_mobile]):
            # address = Address(
            #     user=user,
            #     receiver_name=recv_name,
            #     detail_addr=addr,
            #     zip_code=zip_code,
            #     receiver_mobile=recv_mobile
            # )
            # address.save()
            Address.objects.create(
                user=user,
                receiver_name=recv_name,
                detail_addr=addr,
                zip_code=zip_code,
                receiver_mobile=recv_mobile
            )
        return redirect(reverse("users:address"))


class UserInfoView(LoginRequiredMixin, View):
    """用户中心"""
    def get(self, request):
        user = request.user

        # 获取地址信息
        # Address.objects.all().order_by("-create_time")[0]
        # Address.objects.filter().order_by("-create_time")

        try:
            address = user.address_set.latest("create_time")
        except Address.DoesNotExist:
            # 如果地址信息不存在
            address = None

        # 从django_redis中拿到一个与redis的连接对象
        redis_conn = get_redis_connection("default")

        # 从redis中查询用户的历史记录信息
        sku_ids = redis_conn.lrange("history_%s" % user.id, 0, 4)

        # sku_ids = [5,6,3,9,1]

        # 从数据库中查询商品的信息
        # select * from goods_sku where id in ()
        # skus = GoodsSKU.objects.filter(id__in=sku_ids)

        skus = []
        for sku_id in sku_ids:  # [5,6,3,9,1]
            sku = GoodsSKU.objects.get(id=sku_id)
            skus.append(sku)

        # 形成模板所用的变量，渲染模板
        context = {
            "address": address,
            "skus": skus   # [5,6,3,9,1]
        }
        return render(request, "user_center_info.html", context)














