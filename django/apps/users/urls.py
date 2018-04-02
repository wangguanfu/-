from django.conf.urls import url

from users import views
from django.contrib.auth.decorators import login_required

urlpatterns = [
    # url(r'^register$', views.register, name="register"),
    url(r'^register$', views.RegisterView.as_view(), name="register"),
    url(r'^active/(?P<token>.+)$', views.ActiveView.as_view(), name="active"),
    url(r'^login$', views.LoginView.as_view(), name="login"),
    url(r'^logout$', views.LogoutView.as_view(), name="logout"),
    # url(r'^address$', login_required(views.AddressView.as_view()), name="address"),
    url(r'^address$', views.AddressView.as_view(), name="address"),
    url(r'^info$', views.UserInfoView.as_view(), name="info"),
]


解释一下 Django 和 Tornado 的关系、差别

Django 框架的核心组件有：
用于创建模型的对象关系映射为最终用户设计的完美管理界面一流的 URL  
设计设计者友好的模板语言缓存系统等等
它鼓励快速开发,并遵循MVC设计。Django遵守 BSD版权，最新发行版本是 Django1.4，
于2012年03月23日发布.Django的主要目的是简便、快速的开 发数据库驱动的网站。它强调代码复用,
多个组件可以很方便的以“插件” 形式服务于整个框架，Django有许多功能强大的第三方插件，你甚至可以
 很方便的开发出自己的工具包。这使得Django具有很强的可扩展性。
 它还 强调快速开发和DRY(Do Not RepeatYourself)原则。
Tornado 和现在的主流 Web 服务器框架（包括大多数Python 的框架）有 着明显的区别：
它是非阻塞式服务器，而且速度相当快。得利于其非阻塞 的方式和对epoll的运用，
Tornado 每秒可以处理数以千计的连接，这意味 着对于实时 Web服务来说，
Tornado 是一个理想的 Web 框架。我们开发这 个 Web 服务器的主要目的就是为了处理 
FriendFeed 的实时功能 ――在 
 FriendFeed 的应用里每一个活动用户都会保持着一个服务器连接。
 （关于 如何扩容 服务器，以处理数以千计的客户端的连接的问题。



新权限流程：
1. 配置url，写视图函数
2. admin后台录入权限，分配
3. 用户重新登录

权限的获取：
1. 用户登录,检测用户
2. 用户登录成功，则获取用户的权限列表（init_permission），并放置于session
3. 再次范围则中间件检测
获取权限就是在init_permission

















































