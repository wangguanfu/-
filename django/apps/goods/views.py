from django.shortcuts import render, redirect
from django.views.generic import View
from goods.models import GoodsCategory, IndexGoodsBanner, IndexPromotionBanner
from goods.models import IndexCategoryGoodsBanner, GoodsSKU, Goods
from django.core.cache import cache
from django_redis import get_redis_connection
from django.core.urlresolvers import reverse
from django.http import Http404
from django.core.paginator import Paginator, EmptyPage
import json

# Create your views here.


class BaseCartView(View):
    """提供购物车数据统计功能"""
    def get_cart_num(self, request):
        cart_num = 0

        if request.user.is_authenticated():
            # 如果用户登录，
            # 从redis中获取用户的购物车数据
            redis_conn = get_redis_connection("default")
            user_id = request.user.id
            # 返回字典
            cart = redis_conn.hgetall("cart_%s" % user_id)
            # {"sku_1": "11", "sku_2": "10"}
            for value in cart.values():
                cart_num += int(value)
        else:
            # 用户未登录，从cookie中获取购物车数据
            cart_json = request.COOKIES.get("cart")
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}

            # 遍历cart字典，对商品数量进行求和
            for val in cart.values():
                cart_num += val

        return cart_num


class IndexView(BaseCartView):
    """主页"""
    def get(self, request):
        # 先尝试从缓存中读取数据
        context = cache.get("index_page_data")

        # 如果缓存中没有数据，再查询
        if context is None:
            print("没有缓存数据， 查询了数据库")
            # 查询数据库，获取需要的数据放到模板中

            # 商品分类信息
            categorys = GoodsCategory.objects.all()

            # 首页轮播图信息, 按照index进行排序
            index_goods_banners = IndexGoodsBanner.objects.all().order_by("index")[:4]

            # 活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by("index")[:2]

            # 分类商品信息
            for category in categorys:
                title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by("index")
                category.title_banners = title_banners

                image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by("index")
                category.image_banners = image_banners

            context = {
                "categorys": categorys,
                "index_banners": index_goods_banners,
                "promotion_banners": promotion_banners,
            }

            # 设置缓存数据
            #           名字              内容      有效期
            cache.set("index_page_data", context, 3600)

        # 购物车数据
        cart_num = self.get_cart_num(request)

        # 处理模板
        context.update(cart_num=cart_num)

        return render(request, "index.html", context)


class DetailView(BaseCartView):
    """商品详细信息页面"""
    def get(self, request, sku_id):
        # 尝试获取缓存数据
        context = cache.get("detail_%s" % sku_id)
        # 如果缓存不存在
        if context is None:
            try:
                # 获取商品信息
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # from django.http import Http404
                # raise Http404("商品不存在!")
                return redirect(reverse("goods:index"))

            # 获取类别
            categorys = GoodsCategory.objects.all()

            # 从订单中获取评论信息
            sku_orders = sku.ordergoods_set.all().order_by('-create_time')[:30]
            if sku_orders:
                for sku_order in sku_orders:
                    sku_order.ctime = sku_order.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    sku_order.username = sku_order.order.user.username
            else:
                sku_orders = []

            # 获取最新推荐
            new_skus = GoodsSKU.objects.filter(category=sku.category).order_by("-create_time")[:2]

            # 获取其他规格的商品
            goods_skus = sku.goods.goodssku_set.exclude(id=sku_id)

            context = {
                "categorys": categorys,
                "sku": sku,
                "orders": sku_orders,
                "new_skus": new_skus,
                "goods_skus": goods_skus
            }

            # 设置缓存
            cache.set("detail_%s" % sku_id, context, 3600)

        # 购物车数量
        cart_num = self.get_cart_num(request)

        # 浏览记录
        # 如果是登录的用户
        if request.user.is_authenticated():
            redis_conn = get_redis_connection("default")
            user_id = request.user.id
            # 移除已经存在的本商品浏览记录
            redis_conn.lrem("history_%s" % user_id, 0, sku_id)
            # 添加新的浏览记录
            redis_conn.lpush("history_%s" % user_id, sku_id)
            # 只保存最多5条记录
            redis_conn.ltrim("history_%s" % user_id, 0, 4)

        context.update({"cart_num": cart_num})

        return render(request, 'detail.html', context)


# /list/(商品类别id)/(页数)?sort=
class ListView(BaseCartView):
    """商品列表页面"""
    def get(self, request, category_id, page):
        # 商品类别 顺序  页数
        sort = request.GET.get("sort", "default")

        if sort not in ("price", "hot"):
            sort = "default"

        # 校验参数
        # 判断类别是否存在
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            # 类别不存在
            return redirect(reverse("goods:index"))

        # 根据参数 查询数据库
        # 购物车数量
        cart_num = self.get_cart_num(request)

        # 分类信息
        categorys = GoodsCategory.objects.all()

        # 分类的新品推荐
        new_skus = GoodsSKU.objects.filter(category=category).order_by("-create_time")[:2]

        # 分类的商品, 排序
        if sort == "price":
            skus = GoodsSKU.objects.filter(category=category).order_by("price")
        elif sort == "hot":
            skus = GoodsSKU.objects.filter(category=category).order_by("-sales")
        else:
            skus = GoodsSKU.objects.filter(category=category)

        # 分页
        paginator = Paginator(skus, 1)

        page = int(page)
        try:
            page_skus = paginator.page(page)
        except EmptyPage:
            # 表示用户请求的页数不存在
            page_skus = paginator.page(1)
            page = 1

        # 页数
        # 如果总页数小于5页  paginator.num_pages < 5
        # 如果总页数大于5页  当前页数属于前3页 page <=3
        # 如果总页数大于5页  当前页数属于最后3页  paginator.num_pages - page <3
        # 其他
        num_pages = paginator.num_pages  # 总页数
        if num_pages < 5:
            # 如果总页数小于5页  paginator.num_pages < 5
            page_list = range(1, num_pages+1)
        elif page <= 3:
            # 如果总页数大于5页  当前页数属于前3页 page <=3
            page_list = range(1, 6)  # [1,2,3,4,5]
        elif paginator.num_pages - page < 3:
            # 如果总页数大于5页  当前页数属于最后3页  paginator.num_pages - page <3
            page_list = range(num_pages-4, num_pages+1)
        else:
            page_list = range(page-2, page+3)

        # 处理模板
        context = {
            "category": category,
            "categorys": categorys,
            "new_skus": new_skus,
            "page_skus": page_skus,
            "page_list": page_list,  # 页码
            "sort": sort,
            "cart_num": cart_num
        }

        return render(request, "list.html", context)
















