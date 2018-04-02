from django.contrib import admin
from goods.models import GoodsCategory, Goods, GoodsSKU, IndexPromotionBanner, IndexCategoryGoodsBanner
from celery_tasks.tasks import generate_static_index_html
from django.core.cache import cache

# Register your models here.


class BaseAdmin(admin.ModelAdmin):
    """IndexPromotionBanner的后台管理类"""
    def save_model(self, request, obj, form, change):
        """后台保存对象数据时调用"""
        # obj是要保存的对象数据
        # 将数据保存到数据库中
        obj.save()

        # 调用celery，让celery异步生成静态主页html文件
        generate_static_index_html.delay()

        # 清除缓存数据
        cache.delete("index_page_data")

    def delete_model(self, request, obj):
        """后台删除对象数据时调用"""
        # 在数据库中删除数据
        obj.delete()

        # 调用celery，让celery异步生成静态主页html文件
        generate_static_index_html.delay()

        # 清除缓存数据
        cache.delete("index_page_data")


class IndexPromotionBannerAdmin(BaseAdmin):
    pass


class IndexCategoryGoodsBannerAdmin(BaseAdmin):
    pass


admin.site.register(GoodsCategory)
admin.site.register(Goods)
admin.site.register(GoodsSKU)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(IndexCategoryGoodsBanner, IndexCategoryGoodsBannerAdmin)
