from django.shortcuts import render, redirect
from django.views.generic import View
from utils.views import LoginRequiredMixin, LoginRequiredJsonMixin, TransactionAtomicMixin
from django.core.urlresolvers import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from users.models import Address
from django.http import JsonResponse
from orders.models import OrderInfo, OrderGoods
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.core.cache import cache
from alipay import AliPay
from django.conf import settings
import os

# Create your views here.


class PlaceOrderView(LoginRequiredMixin, View):
    """订单确认页面"""
    def post(self, request):
        # 获取参数
        sku_ids = request.POST.getlist("sku_ids")  #  要购买的商品id  [1,2,3,4,5]
        count = request.POST.get("count")  # 商品的数量,从商品详情页面进入这个视图时需要传递，从购物车页面进入这个视图时不需要传递
                                           # 商品详情页面的商品只有一个，所以数量也只有一个

        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse("cart:info"))

        redis_conn = get_redis_connection("default")
        user_id = request.user.id

        skus = []
        total_count = 0
        total_skus_amount = 0
        trans_cost = 10  # 邮费，暂时写死

        # 查询商品数据
        if count is None:
            # 如果是从购物车页面过来，商品的数量需要从redis中获取
            cart = redis_conn.hgetall("cart_%s" % user_id)
            total_amount = 0  # 包含了邮费和商品总金额的数值
            # 遍历商品id，获取商品信息
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 跳转到购物车页面
                    return redirect(reverse("cart:info"))
                # 读取商品的数量
                sku_count = cart.get(sku_id.encode())
                sku_count = int(sku_count)

                # 计算商品的金额
                amount = sku.price * sku_count
                sku.amount = amount
                sku.count = sku_count
                skus.append(sku)
                total_count += sku_count
                total_skus_amount += amount
        else:
            # 如果是从商品详情页面过来，商品的数量直接就是count参数值
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 跳转到购物车页面
                    return redirect(reverse("cart:info"))

                try:
                    sku_count = int(count)
                except Exception:
                    # 跳回到商品的详情页面
                    return redirect(reverse("goods:detail", args=(sku_id,)))

                # 判断库存
                if sku_count > sku.stock:
                    # 跳回到商品的详情页面
                    return redirect(reverse("goods:detail", args=(sku_id,)))

                # 计算商品的金额
                amount = sku.price * sku_count
                sku.amount = amount
                sku.count = sku_count
                skus.append(sku)
                total_count += sku_count
                total_skus_amount += amount

                # 将商品存放到购物车中
                redis_conn.hset("cart_%s" % user_id, sku_id, sku_count)

        total_amount = total_skus_amount + trans_cost

        # 地址信息
        # address = Address.objects.filter(user_id=user_id)
        try:
            address = Address.objects.filter(user=request.user).latest("create_time")
        except Address.DoesNotExist:
            address = None

        # 返回前端页面
        context = {
            "skus": skus,
            "total_count": total_count,
            "total_skus_amount": total_skus_amount,
            "total_amount": total_amount,
            "trans_cost": trans_cost,
            "address": address,
            "sku_ids": ",".join(sku_ids)
        }
        return render(request, "place_order.html", context)


class CommitOrderView(LoginRequiredJsonMixin, TransactionAtomicMixin, View):
    """提交订单"""
    def post(self, request):
        # 获取参数
        #  user 地址id  支付方式  商品id  数量(从购物车中获取）
        user = request.user
        address_id = request.POST.get("address_id")
        sku_ids = request.POST.get("sku_ids")  # "1,2,3,4"
        pay_method = request.POST.get("pay_method")

        # 校验参数
        if not all([address_id, sku_ids, pay_method]):
            return JsonResponse({"code": 2, "message": "参数缺失"})

        # 判断地址是否存在
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return JsonResponse({"code": 3, "message": "地址不存在"})

        # 判断支付方式
        pay_method = int(pay_method)
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({"code": 4, "message": "支付方式错误"})

        # 判断商品
        sku_ids = sku_ids.split(",")   # ["1", "2"]
        redis_conn = get_redis_connection("default")
        cart = redis_conn.hgetall("cart_%s" % user.id)

        # 创建一个订单基本信息表数据

        # 自定义的order_id  "20171026111111用户id"
        order_id = timezone.now().strftime("%Y%m%d%H%M%S") + str(user.id)

        # 创建事务保存点
        save_id = transaction.savepoint()
        try:
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                address=address,
                total_amount=0,
                trans_cost=10,
                pay_method=pay_method,
            )

            total_count = 0  # 总数
            total_amount = 0  # 总金额
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 回退的保存点的状态
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"code": 5, "message": "商品有误"})

                    # 获取订购的商品数量，判断库存
                    sku_count = cart.get(sku_id.encode())
                    sku_count = int(sku_count)
                    if sku_count > sku.stock:
                        # 回退的保存点的状态
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"code": 6, "message": "库存不足"})

                    # 减少商品的库存, 增加商品的销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - sku_count
                    new_sales = sku.sales + sku_count
                    # update操作会返回受影响的行数，即更新成功的函数
                    result = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if result == 0 and i < 2:
                        # 表示更新失败
                        continue
                    elif result == 0 and i == 2:
                        # 表示尝试三次失败
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"code": 7, "message": "下单失败"})

                    # 保存订单商品
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=sku_count,
                        price=sku.price,
                    )

                    # 累计计算总数
                    total_count += sku_count
                    # 累计计算总金额
                    total_amount += (sku.price * sku_count)

                    # 跳出三次循环，处理下一个商品
                    break

            # 修改订单基本信息表中的统计数据字段
            order.total_count = total_count
            order.total_amount = total_amount + 10
            order.save()

        except Exception:
            # 出现任何异常，都要回退的保存点的状态
            transaction.savepoint_rollback(save_id)
            return JsonResponse({"code": 8, "message": "下单失败"})

        # 执行成功，提交事务
        transaction.savepoint_commit(save_id)

        # 保存最新的购物车数据
        redis_conn.hdel("cart_%s" % user.id, *sku_ids)  # 删除订购的商品

        # 返回前端json状态
        return JsonResponse({"code": 0, "message": "创建订单成功"})


class UserOrdersView(LoginRequiredMixin, View):
    """用户订单"""
    def get(self, request, page):
        user = request.user
        # 查询订单
        orders = user.orderinfo_set.all().order_by("-create_time")

        for order in orders:
            order.status_name = OrderInfo.ORDER_STATUS[order.status]
            order.pay_method_name = OrderInfo.PAY_METHODS[order.pay_method]
            order.skus = []
            order_skus = order.ordergoods_set.all()
            for order_sku in order_skus:
                sku = order_sku.sku
                sku.count = order_sku.count
                sku.amount = sku.price * sku.count
                order.skus.append(sku)

        # 分页
        paginator = Paginator(orders, 3)
        # 获取页码的列表
        pages = paginator.page_range
        # 获取总页数
        num_pages = paginator.num_pages
        # 当前页转化为数字
        page = int(page)

        # 1.如果总页数<=5
        # 2.如果当前页是前3页
        # 3.如果当前页是后3页,
        # 4.既不是前3页，也不是后3页
        if num_pages <= 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif (num_pages - page) <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 取第page页的内容 has_previous has_next number
        page_orders = paginator.page(page)

        context = {
            "orders": page_orders,
            "page": page,
            "pages": pages
        }

        return render(request, "user_center_order.html", context)


class CommentView(LoginRequiredMixin, View):
    """订单评论"""
    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        order.status_name = OrderInfo.ORDER_STATUS[order.status]
        order.skus = []
        order_skus = order.ordergoods_set.all()
        for order_sku in order_skus:
            sku = order_sku.sku
            sku.count = order_sku.count
            sku.amount = sku.price * sku.count
            order.skus.append(sku)

        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        for i in range(1, total_count + 1):
            sku_id = request.POST.get("sku_%d" % i)
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

            # 清除商品详情缓存
            cache.delete("detail_%s" % sku_id)

        order.status = OrderInfo.ORDER_STATUS_ENUM["FINISHED"]
        order.save()

        return redirect(reverse("orders:info", kwargs={"page": 1}))


class PayView(LoginRequiredJsonMixin, View):
    """支付宝支付"""
    def post(self, request):
        """"""
        # 订单id
        order_id = request.POST.get("order_id")

        if not order_id:
            return JsonResponse({"code": 2, "message": "缺失订单号"})

        # 获取订单的信息
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"],
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"])
        except OrderInfo.DoesNotExist:
            return JsonResponse({"code": 3, "message": "订单信息有误"})

        # 创建用于进行支付宝支付的工具对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, "apps/orders/app_private_key.pem"),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, "apps/orders/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False  配合沙箱模式使用
        )

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),  # 将Decimal类型转换为字符串交给支付宝
            subject="天天生鲜%s" % order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 让用户进行支付的支付宝页面网址
        url = settings.ALIPAY_URL + "?" + order_string

        return JsonResponse({"code": 0, "message": "请求支付成功", "url": url})


class CheckPayStatusView(LoginRequiredJsonMixin, View):
    """查询支付结果"""
    def get(self, request):
        # 订单编号
        order_id = request.GET.get("order_id")

        if not order_id:
            return JsonResponse({"code": 2, "message": "缺失订单号"})

        # 获取订单的信息
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"],
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"])
        except OrderInfo.DoesNotExist:
            return JsonResponse({"code": 3, "message": "订单信息有误"})

        # 创建用于进行支付宝支付的工具对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, "apps/orders/app_private_key.pem"),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, "apps/orders/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False  配合沙箱模式使用
        )

        while True:
            # 调用alipay工具查询支付结果
            response = alipay.api_alipay_trade_query(order_id)  # response是一个字典

            # 判断支付结果
            code = response.get("code")  # 支付宝接口调用成功或者错误的标志
            trade_status = response.get("trade_status")  # 用户支付的情况

            if code == "10000" and trade_status == "TRADE_SUCCESS":
                # 表示用户支付成功
                # 修改订单的状态，变为待评论状态
                order.status = OrderInfo.ORDER_STATUS_ENUM["UNCOMMENT"]

                # 更新订单的支付宝交易编号
                order.trade_id = response.get("trade_no")
                order.save()

                # 返回前端json，通知支付成功
                return JsonResponse({"code": 0, "message": "支付成功"})

            elif code == "40004" or (code == "10000" and trade_status == "WAIT_BUYER_PAY"):
                # 表示支付宝接口调用暂时失败，（支付宝的支付订单还未生成） 后者 等待用户支付
                # 继续查询
                continue
            else:
                # 支付失败
                # 返回支付失败的通知
                return JsonResponse({"code": 4, "message": "支付失败"})



















