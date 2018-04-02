from celery import Celery
import os

os.environ["DJANGO_SETTINGS_MODULE"] = "dailyfresh_14.settings"

# 放到celery服务器上时将注释打开
# import django
# django.setup()

from django.core.mail import send_mail
from django.conf import settings
from goods.models import GoodsCategory, IndexGoodsBanner, IndexPromotionBanner
from goods.models import IndexCategoryGoodsBanner
from django.template import loader

# celery -A celery_tasks.tasks worker -l info


# 创建celery应用对象
app = Celery("celery_tasks.tasks", broker="redis://10.211.55.5/4")


@app.task
def send_active_email(to_email, user_name, token):
    """发送激活邮件"""
    subject = "天天生鲜用户激活"  # 标题
    body = ""  # 文本邮件体
    sender = settings.EMAIL_FROM  # 发件人
    receiver = [to_email]  # 接收人
    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/users/active/%s">' \
                'http://127.0.0.1:8000/users/active/%s</a></p>' % (user_name, token, token)
    send_mail(subject, body, sender, receiver, html_message=html_body)


@app.task
def generate_static_index_html():
    """生成静态的html主页"""
    # 查询数据库，获取需要的数据放到模板中

    # 商品分类信息
    categorys = GoodsCategory.objects.all()

    # 首页轮播图信息, 按照index进行排序
    index_goods_banners = IndexGoodsBanner.objects.all().order_by("index")

    # 活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by("index")

    # 分类商品信息
    for category in categorys:
        title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by("index")
        category.title_banners = title_banners

        image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by("index")
        category.image_banners = image_banners

    # 购物车数据
    cart_num = 0

    # 处理模板
    context = {
        "categorys": categorys,
        "index_banners": index_goods_banners,
        "promotion_banners": promotion_banners,
        "cart_num": cart_num
    }

    # 加载模板
    template = loader.get_template("static_index.html")
    # 填充数据
    html_data = template.render(context)

    # 保存成html文件
    file_path = os.path.join(settings.STATICFILES_DIRS[0], "index.html")

    with open(file_path, "w") as f:
        f.write(html_data)

    #
    # file = open(file_path, "w")
    # try:
    #     file.write(html_data)
    # except Exception:
    #     pass
    # finally::
    #     file.close()
















