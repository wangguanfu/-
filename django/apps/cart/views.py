from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
import json

# Create your views here.


class AddCartView(View):
    """加入购物车"""
    def post(self, request):
        # # 判断用户是否登录
        # if not request.user.is_authenticated():
        #     # 用户未登录
        #     return JsonResponse({"code": 1, "message": "用户未登录"})

        # sku_id 商品id
        sku_id = request.POST.get("sku_id")
#后端严验证用户名和密码匹配后, 将用户信息存到session里面, response带上session_id给前端设置cookie就完了.
        # count 商品数量
        count = request.POST.get("count")

        # 检验参数
        if not all([sku_id, count]):
            return JsonResponse({"code": 2, "message": "参数不完整"})

        # 判断商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 表示商品不存在
            return JsonResponse({"code": 3, "message": "商品不存在"})

        # 判断count是整数
        try:
            count = int(count)
        except Exception:
            return JsonResponse({"code": 4, "message": "参数错误"})

        # 判断库存
        if count > sku.stock:
            return JsonResponse({"code": 5, "message": "库存不足"})

        if request.user.is_authenticated():
            # 如果用户已登录，则保存购物车数据到redis中

            # 用户id
            user_id = request.user.id

            # 操作redis，保存购物车数据
            # "cart_用户id"： {"sku_1": 10, "sku_2": 11}
            # 先尝试从用户的购物车中获取这个商品的数量
            # 如果购物车中不存在这个商品，则直接添加购物车记录
            # 否则，需要进行数量的累计，在添加到购物车记录中
            redis_conn = get_redis_connection("default")
            origin_count = redis_conn.hget("cart_%s" % user_id, sku_id)  # 原有数量

            if origin_count is not None:
                count += int(origin_count)

            redis_conn.hset("cart_%s" % user_id, sku_id, count)

            # 为了方便前端展示购物车数量，所以查询一下购物车总数
            cart_num = 0
            cart = redis_conn.hgetall("cart_%s" % user_id)
            for val in cart.values():
                cart_num += int(val)

            # 采用json返回给前端
            return JsonResponse({"code": 0, "message": "添加购物车成功", "cart_num": cart_num})
        else:
            # 如果用户未登录，则将购物车数据保存到cookie中
            # 尝试先从cookie的购物车信息中获取当前商品的记录
            cart_json = request.COOKIES.get("cart")  # 取出json字符串格式的购物车数据
            # 判断cart_json是否存在，用户可能从来没有操作过购物车
            if cart_json is not None:
                cart = json.loads(cart_json)  # cart是字典类型
                # { “sku_1”:10, “sku_2”: 20  }
            else:
                cart = {}

            # 如果cart中有这个商品的记录信息，
            if sku_id in cart:
                # 把数量进行求和,
                origin_count = cart[sku_id]  # 原有数量
                count += origin_count
            # 存放到cart字典中
            cart[sku_id] = count

            # 将cart购物车字典数据转换为json字符串
            new_cart_json = json.dumps(cart)

            # 计算购物车的商品总数
            cart_num = 0
            for val in cart.values():
                cart_num += val

            # 将购物车数据存放到cookie中
            response = JsonResponse({"code": 0, "message": "添加购物车成功", "cart_num": cart_num})

            response.set_cookie("cart", new_cart_json)

            # 返回处理结果
            return response


class CartInfoView(View):
    """购物车信息"""
    def get(self, request):
        """提供购物车页面"""
        # 业务逻辑， 查询购物车数据
        if not request.user.is_authenticated():
            # 如果用户未登录，从cookie获取数据
            cart_json = request.COOKIES.get("cart")
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                # cookie中不存在购物车数据
                cart = {}
        else:
            # 如果用户已登录，从redis中获取数据
            redis_conn = get_redis_connection("default")
            user_id = request.user.id
            cart = redis_conn.hgetall("cart_%s" % user_id)

        # 遍历cart字典，形成模板所需要的数据
        skus = []
        total_amount = 0  # 总金额
        total_count = 0  # 总数量
        for sku_id, count in cart.items():
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # 商品不存在
                continue
            count = int(count)
            amount = sku.price * count  # Decimal
            sku.amount = amount  # 商品的金额
            sku.count = count  # 商品的数量
            skus.append(sku)
            total_amount += amount
            total_count += count

        # 返回处理结果, 渲染模板
        context = {
            "skus": skus,
            "total_amount": total_amount,
            "total_count": total_count
        }
        return render(request, "cart.html", context)


class UpdateCartView(View):
    """更新购物车数据"""
    def post(self, request):
        # 获取参数
        sku_id = request.POST.get("sku_id")  # 商品id
        count = request.POST.get("count")  # 商品数量

        # 校验参数
        if not all([sku_id, count]):
            return JsonResponse({"code": 1, "message": "参数不完整"})

        # 判断商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"code": 2, "message": "商品不存在"})

        # count是否是整数
        try:
            count = int(count)
        except Exception:
            return JsonResponse({"code": 3, "message": "数量异常"})

        # 判断库存
        if count > sku.stock:
            return JsonResponse({"code": 4, "message": "库存不足"})

        # 保存购物车数据
        if not request.user.is_authenticated():
            # 如果用户未登录，保存在cookie中
            cart_json = request.COOKIES.get("cart")
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}
            # 将商品的数据保存到购物车中
            cart[sku_id] = count
            # 将购物车数据保存到cookie中
            response = JsonResponse({"code": 0, "message": "修改成功"})
            response.set_cookie("cart", json.dumps(cart))
            return response
        else:
            # 如果用户已登录，保存在redis中
            user_id = request.user.id
            redis_conn = get_redis_connection("default")
            redis_conn.hset("cart_%s" % user_id, sku_id, count)
            return JsonResponse({"code": 0, "message": "修改成功"})


class DeleteCartView(View):
    """删除购物车数据"""
    def post(self, request):
        sku_id = request.POST.get("sku_id")  # 商品id

        if not sku_id:
            return JsonResponse({"code": 1, "message": "参数缺少"})

        # 从购物车中删除数据
        if not request.user.is_authenticated():
            # 用户未登录 ，cookies
            cart_json = request.COOKIES.get("cart")
            if cart_json is not None:
                cart = json.loads(cart_json)
                # 如果购物车中有这个商品，则删除
                if sku_id in cart:
                    del cart[sku_id]
                    response = JsonResponse({"code": 0, "message": "删除成功"})
                    response.set_cookie("cart", json.dumps(cart))
                    return response
        else:
            # 用户已登录，redis
            redis_conn = get_redis_connection("default")
            user_id = request.user.id
            # 让redis删除sku_id对应的数据，如果redis中不存在，redis会忽略掉
            redis_conn.hdel("cart_%s" % user_id, sku_id)

        return JsonResponse({"code": 0, "message": "删除成功"})







